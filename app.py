"""왓챠 콘텐츠 매출 분석 MVP (엑셀 업로드 버전).

연도별 '콘텐츠 매직시트' 엑셀 파일(최대 7개, 2020~2026)을 업로드하고
콘텐츠 ID 1~3개 + 매출 종류 필터를 지정하면 2020~2026 월별 매출을
피벗 테이블 / 연간 요약 / 비교 라인 차트 / 급락 지점으로 보여준다.
"""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Iterable

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# --------------------------------------------------------------------------
# 설정
# --------------------------------------------------------------------------

SUPPORTED_YEARS = range(2020, 2027)
YEAR_PATTERN = re.compile(r"(20\d{2})")

# 왓챠 '콘텐츠 매직시트' 전용 상수
PREFERRED_SHEET_KEYWORDS = ["confidential", "매출", "sales", "revenue"]
HEADER_KEY_COLUMNS = {"id", "title", "type", "category", "콘텐츠id", "매출종류"}
REVENUE_TYPE_VALUE = "정산금(rs기준)"  # type 컬럼에서 이 값만 매출로 본다

ID_COLUMN_CANDIDATES = [
    "id", "content_id", "contents_id", "콘텐츠 id", "콘텐츠 ID", "콘텐츠id",
    "content id",
]
TITLE_COLUMN_CANDIDATES = [
    "title", "content_title", "contents_title", "콘텐츠 제목", "제목",
    "콘텐츠제목", "name", "콘텐츠명",
]
TYPE_COLUMN_CANDIDATES = ["type", "구분", "유형"]
SALES_CATEGORY_COLUMN_CANDIDATES = ["매출 종류", "매출종류", "bill_type", "category_bill"]

MONTH_NAMES_EN_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# FLAT 예상 금액 계산용
FLAT_DEPRECIATION = 0.7  # 감가율
FLAT_YEAR_MULTIPLIERS = {"1년": 1, "3년": 3, "5년": 5}

_LOGO_PATH = Path(__file__).parent / "assets" / "watcha_w.png"

st.set_page_config(
    page_title="WATCHA SVOD 콘텐츠 매출 분석",
    page_icon=str(_LOGO_PATH) if _LOGO_PATH.exists() else "📊",
    layout="wide",
)

if _LOGO_PATH.exists():
    try:
        st.logo(str(_LOGO_PATH), size="large")
    except Exception:
        pass


# --------------------------------------------------------------------------
# 글로벌 테마 (왓챠피디아 톤: 다크 차콜 + 핑크 액센트 + 둥근 카드)
# --------------------------------------------------------------------------

_WATCHA_PINK = "#FF3D7F"
_PINK_SOFT = "#FFB3CC"
_PINK_TINT = "#FFE5EE"
_BG_PAGE = "#FFFFFF"
_BG_SOFT = "#FAFAFA"
_BG_CARD = "#F7F7F7"
_BORDER = "#E5E5E5"
_BORDER_SOFT = "#ECECEC"
_TEXT = "#1A1A1A"
_TEXT_MUTED = "#6B6B6B"
# Plotly 차트용 폰트 스택 (CSS 와 동일한 fallback 체인)
_PLOTLY_FONT_FAMILY = (
    '"Apple SD Gothic Neo", -apple-system, BlinkMacSystemFont, '
    '"Pretendard", "Malgun Gothic", "Segoe UI", Roboto, sans-serif'
)

st.markdown(
    f"""
    <style>
    /* 글로벌 폰트: Apple SD Gothic Neo (macOS/iOS 기본 한글),
       다른 OS·브라우저는 시스템·Pretendard·Malgun Gothic 으로 fallback */
    html, body, .stApp, [class*="st-"], button, input, select, textarea, label {{
        font-family: "Apple SD Gothic Neo", -apple-system, BlinkMacSystemFont,
            "Pretendard", "Malgun Gothic", "Segoe UI", Roboto, sans-serif !important;
    }}

    /* 페이지: 흰톤 베이스 (원복) */
    .stApp {{
        background: linear-gradient(180deg, {_BG_PAGE} 0%, {_BG_SOFT} 240px) no-repeat;
        color: {_TEXT};
    }}
    .block-container {{
        padding-top: 2rem;
        padding-bottom: 4rem;
        max-width: 1240px;
    }}

    /* 타이포 — 부드럽고 둥근 위계 */
    h1, h2, h3 {{ color: {_TEXT}; }}
    h1 {{ font-weight: 800; letter-spacing: -0.02em; }}
    h2 {{
        font-weight: 700;
        letter-spacing: -0.01em;
        border-left: none !important;
        padding-left: 0 !important;
        margin-top: 2.2rem !important;
        position: relative;
        padding-left: 1.4rem !important;
    }}
    h2::before {{
        content: "";
        position: absolute;
        left: 0;
        top: 50%;
        transform: translateY(-50%);
        width: 0.7rem;
        height: 0.7rem;
        border-radius: 999px;
        background: linear-gradient(135deg, {_WATCHA_PINK} 0%, {_PINK_SOFT} 100%);
        box-shadow: 0 0 0 4px {_PINK_TINT};
    }}
    h3 {{ font-weight: 600; color: #4A2630; }}
    .stCaption, [data-testid="stCaptionContainer"] {{
        color: {_TEXT_MUTED} !important;
    }}

    /* 디바이더 — 얇고 핑크 그라데이션 */
    hr {{
        border: none !important;
        height: 1px !important;
        background: linear-gradient(90deg, transparent 0%, {_BORDER} 30%, {_PINK_SOFT} 50%, {_BORDER} 70%, transparent 100%) !important;
        opacity: 0.9;
    }}

    /* 사이드바 — 미세하게 더 회색 톤 */
    [data-testid="stSidebar"] {{
        background-color: {_BG_SOFT};
        border-right: 1px solid {_BORDER_SOFT};
    }}
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {{
        border-left: none !important;
        padding-left: 0 !important;
        font-size: 0.95rem;
        color: {_TEXT_MUTED};
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }}
    [data-testid="stSidebar"] h2::before {{ display: none; }}

    /* 버튼 — 핑크 그라데이션 + 부드러운 그림자 */
    .stButton > button[kind="primary"],
    .stDownloadButton > button[kind="primary"],
    div[data-testid="stFormSubmitButton"] > button {{
        background: linear-gradient(135deg, {_WATCHA_PINK} 0%, #FF6BA0 100%);
        color: white;
        border: none;
        border-radius: 999px;
        padding: 0.6rem 1.5rem;
        font-weight: 700;
        letter-spacing: 0.01em;
        box-shadow: 0 6px 18px rgba(255, 61, 127, 0.25);
        transition: transform 0.08s ease, box-shadow 0.15s ease, filter 0.15s ease;
    }}
    .stButton > button[kind="primary"]:hover,
    .stDownloadButton > button[kind="primary"]:hover,
    div[data-testid="stFormSubmitButton"] > button:hover {{
        filter: brightness(1.05);
        transform: translateY(-2px);
        box-shadow: 0 10px 24px rgba(255, 61, 127, 0.32);
    }}
    .stButton > button[kind="secondary"],
    .stDownloadButton > button[kind="secondary"] {{
        border-radius: 999px;
        border: 1.5px solid {_BORDER};
        background-color: white;
        color: {_TEXT};
        font-weight: 600;
        transition: background-color 0.15s ease, border-color 0.15s ease;
    }}
    .stButton > button[kind="secondary"]:hover,
    .stDownloadButton > button[kind="secondary"]:hover {{
        background-color: {_PINK_TINT};
        border-color: {_PINK_SOFT};
    }}

    /* 입력 위젯 — 둥글게 + 핑크 포커스 */
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    [data-testid="stMultiSelect"] div[data-baseweb="select"] > div {{
        background-color: white;
        border-radius: 14px;
        border: 1.5px solid {_BORDER_SOFT};
        transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }}
    [data-testid="stTextInput"] input:focus,
    [data-testid="stNumberInput"] input:focus {{
        border-color: {_WATCHA_PINK} !important;
        box-shadow: 0 0 0 4px {_PINK_TINT} !important;
        outline: none !important;
    }}

    /* 사이드바 최소 폭 확장 (위젯 안 텍스트 잘림 방지) */
    [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child {{
        min-width: 300px !important;
    }}

    /* 파일 업로더 — 점선 핑크 보더 + 흰 배경 (내부 layout 은 Streamlit 기본 유지) */
    [data-testid="stFileUploader"] section {{
        border-radius: 18px !important;
        border: 2px dashed {_PINK_SOFT} !important;
        background: white !important;
        transition: background 0.2s ease;
    }}
    [data-testid="stFileUploader"] section:hover {{
        background: {_PINK_TINT} !important;
    }}
    /* 환경/버전에 따라 button 안 텍스트('upload' 등) 가 두 번 렌더되는
       문제를 해결: 기존 자식 모두 가리고 ::after 로 라벨 한 번 주입 */
    [data-testid="stFileUploader"] button {{
        position: relative !important;
        color: transparent !important;
        overflow: hidden !important;
        min-height: 38px !important;
    }}
    [data-testid="stFileUploader"] button > * {{
        visibility: hidden !important;
        pointer-events: none !important;
    }}
    [data-testid="stFileUploader"] button::after {{
        content: "파일 선택";
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        color: {_TEXT};
        font-size: 0.88rem;
        font-weight: 600;
        font-family: inherit;
        letter-spacing: 0;
        visibility: visible !important;
    }}

    /* 메트릭 카드 — 흰 베이스 + 핑크 보더, 호버 시 핑크 그림자 */
    [data-testid="stMetric"] {{
        background-color: white;
        border: 1.5px solid {_BORDER_SOFT};
        border-radius: 20px;
        padding: 1.1rem 1.3rem;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.04);
        transition: transform 0.1s ease, box-shadow 0.15s ease;
    }}
    [data-testid="stMetric"]:hover {{
        transform: translateY(-2px);
        box-shadow: 0 10px 22px rgba(255, 61, 127, 0.12);
    }}
    [data-testid="stMetricValue"] {{
        font-weight: 800;
        letter-spacing: -0.01em;
        color: {_TEXT};
    }}
    [data-testid="stMetricLabel"] {{
        color: {_TEXT_MUTED} !important;
        font-size: 0.82rem !important;
        font-weight: 600;
    }}

    /* expander — 라이트 카드 */
    [data-testid="stExpander"] {{
        background-color: {_BG_CARD};
        border: 1.5px solid {_BORDER_SOFT};
        border-radius: 18px;
        overflow: hidden;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.03);
    }}
    [data-testid="stExpander"] summary {{
        font-weight: 600;
        color: {_TEXT};
    }}
    [data-testid="stExpander"] summary:hover {{
        background-color: {_PINK_TINT};
    }}

    /* 데이터프레임/표 — 라운드 + 옅은 보더 */
    [data-testid="stDataFrame"], [data-testid="stTable"] {{
        border-radius: 16px;
        overflow: hidden;
        border: 1.5px solid {_BORDER_SOFT};
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.03);
    }}

    /* alert(info/warning/success) — 둥글고 핑크 톤 */
    [data-testid="stAlert"] {{
        border-radius: 16px;
        border: 1.5px solid {_BORDER_SOFT};
    }}

    /* 스크롤바 — 핑크 미니멀 */
    ::-webkit-scrollbar {{ width: 10px; height: 10px; }}
    ::-webkit-scrollbar-thumb {{
        background: {_PINK_SOFT};
        border-radius: 999px;
    }}
    ::-webkit-scrollbar-thumb:hover {{ background: {_WATCHA_PINK}; }}
    </style>
    """,
    unsafe_allow_html=True,
)


def _render_title(title: str, *, level: str = "h1") -> None:
    """왓챠 W 로고 + 제목을 바짝 붙여 한 줄로 렌더 (왓챠피디아 톤)."""
    if _LOGO_PATH.exists():
        import base64
        b64 = base64.b64encode(_LOGO_PATH.read_bytes()).decode()
        st.markdown(
            f"""
            <div style="display:flex; align-items:center; gap:14px; margin:0 0 1rem 0;">
                <img src="data:image/png;base64,{b64}"
                     style="width:46px; height:46px; border-radius:14px;
                            box-shadow:0 4px 16px rgba(255,61,127,0.32);" />
                <{level} style="margin:0; line-height:1.1; font-weight:800;
                                 letter-spacing:-0.02em; border-left:none; padding-left:0;">
                    {title}
                </{level}>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f"<{level} style='margin:0;'>{title}</{level}>", unsafe_allow_html=True)


# --------------------------------------------------------------------------
# 비밀번호 게이트
# --------------------------------------------------------------------------

def require_password() -> None:
    if st.session_state.get("authed"):
        return
    try:
        expected = st.secrets.get("app_password", "")
    except Exception:
        expected = ""
    if not expected:
        st.error(
            "⚠️ `app_password` 가 설정되지 않았습니다. "
            "`.streamlit/secrets.toml` 또는 Streamlit Cloud Secrets 에 값을 추가하세요."
        )
        st.stop()

    _render_title("SVOD 콘텐츠 매출 분석")
    st.write("비밀번호를 입력하세요.")
    pw = st.text_input("비밀번호", type="password", label_visibility="collapsed")
    if st.button("입장"):
        if pw == expected:
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("비밀번호가 일치하지 않습니다.")
    st.stop()


# --------------------------------------------------------------------------
# 유틸
# --------------------------------------------------------------------------

def _normalize(s) -> str:
    return re.sub(r"\s+", "", str(s)).lower()


def _find_column(df_columns: Iterable, candidates: Iterable[str]) -> str | None:
    norm_map = {_normalize(c): c for c in df_columns}
    for cand in candidates:
        key = _normalize(cand)
        if key in norm_map:
            return norm_map[key]
    return None


def _extract_month(col) -> int | None:
    """컬럼명에서 월 번호(1~12) 추출. datetime/ISO문자열/한글월/영문축약 모두 지원."""
    # datetime 계열 (pd.Timestamp, datetime.datetime 등)
    m = getattr(col, "month", None)
    if isinstance(m, int) and 1 <= m <= 12:
        return m
    s = str(col).strip()
    # '2025-01-01', '2025.01. 01', '2025/1/1', '2025년 1월' 등
    match = re.match(r"^20\d{2}\s*[\.\-\/년]\s*(\d{1,2})", s)
    if match:
        month = int(match.group(1))
        if 1 <= month <= 12:
            return month
    # '1월', '1', 'Jan', 'month1' 등
    s_norm = _normalize(s)
    for month in range(1, 13):
        candidates = {
            _normalize(f"{month}월"),
            _normalize(MONTH_NAMES_EN_SHORT[month - 1]),
            str(month),
            f"m{month}",
            f"month{month}",
        }
        if s_norm in candidates:
            return month
    return None


def _find_month_columns(df_columns: list) -> list | None:
    """월 1~12 컬럼 자동 감지."""
    try:
        overrides = st.secrets.get("columns", {}).get("months")
    except Exception:
        overrides = None
    if overrides:
        return [c for c in overrides if c in df_columns]

    month_map: dict = {}
    for c in df_columns:
        m = _extract_month(c)
        if m and m not in month_map:
            month_map[m] = c
    if len(month_map) == 12:
        return [month_map[mnum] for mnum in range(1, 13)]
    return None


def _to_number(value) -> float:
    if value is None or value == "" or (isinstance(value, float) and pd.isna(value)):
        return float("nan")
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    if not cleaned or cleaned in {"-", "."}:
        return float("nan")
    try:
        return float(cleaned)
    except ValueError:
        return float("nan")


def _detect_year_from_filename(filename: str) -> int | None:
    for m in YEAR_PATTERN.finditer(filename):
        year = int(m.group(1))
        if year in SUPPORTED_YEARS:
            return year
    return None


# --------------------------------------------------------------------------
# 엑셀 파일 파싱 (Confidential 시트 + 헤더 자동 감지)
# --------------------------------------------------------------------------

def _pick_best_sheet(sheet_names: list[str]) -> str:
    for kw in PREFERRED_SHEET_KEYWORDS:
        for name in sheet_names:
            if kw in str(name).lower():
                return name
    return sheet_names[0]


def _find_header_row(raw: pd.DataFrame, max_check: int = 15) -> int:
    """상단 max_check 행 중 HEADER_KEY_COLUMNS 키워드가 2개 이상 보이는 행을 헤더로."""
    for i in range(min(len(raw), max_check)):
        row_vals = {_normalize(v) for v in raw.iloc[i].tolist() if not pd.isna(v)}
        if len(row_vals & HEADER_KEY_COLUMNS) >= 2:
            return i
    return 0


def _to_month_timestamp(v) -> pd.Timestamp:
    """다양한 형태의 월 값을 pd.Timestamp 로 변환. 실패 시 pd.NaT."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return pd.NaT
    if isinstance(v, pd.Timestamp):
        return v
    if hasattr(v, "year") and hasattr(v, "month"):
        try:
            return pd.Timestamp(v)
        except Exception:
            return pd.NaT
    s = str(v).strip()
    m = re.match(r"^(20\d{2})[\.\-/년]\s*(\d{1,2})[\.\-/월]?\s*(\d{0,2})", s)
    if m:
        try:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3) or 1)
            return pd.Timestamp(f"{y}-{mo:02d}-{d:02d}")
        except Exception:
            return pd.NaT
    try:
        return pd.to_datetime(s, errors="coerce")
    except Exception:
        return pd.NaT


# calamine 엔진이 있으면 시도 (openpyxl 대비 5~10배 빠름). 어떤 단계든 실패 시 openpyxl 로 자동 fallback.
_PRIMARY_ENGINE = "openpyxl"
try:
    import python_calamine  # noqa: F401
    _PRIMARY_ENGINE = "calamine"
except Exception:
    pass


def _read_excel_safe(*args, **kwargs) -> pd.DataFrame:
    """pd.read_excel + 엔진 fallback. 1차 엔진이 어떤 이유로든 실패하면 openpyxl 로 재시도."""
    try:
        return pd.read_excel(*args, engine=_PRIMARY_ENGINE, **kwargs)
    except Exception:
        if _PRIMARY_ENGINE == "openpyxl":
            raise
        return pd.read_excel(*args, engine="openpyxl", **kwargs)


def _excel_file_safe(data: bytes) -> pd.ExcelFile:
    try:
        return pd.ExcelFile(BytesIO(data), engine=_PRIMARY_ENGINE)
    except Exception:
        if _PRIMARY_ENGINE == "openpyxl":
            raise
        return pd.ExcelFile(BytesIO(data), engine="openpyxl")


@st.cache_data(show_spinner=False)
def _get_sheet_names(data: bytes) -> list[str]:
    """엑셀의 시트 이름 목록만 반환 (가벼움, 워크북 구조만 파싱)."""
    try:
        return list(_excel_file_safe(data).sheet_names)
    except Exception:
        return []


@st.cache_data(show_spinner=False)
def _read_confidential_sheet(data: bytes) -> pd.DataFrame:
    """Confidential 시트만 단독 로딩 (viewing_log 안 읽음)."""
    sheet_names = _get_sheet_names(data)
    if not sheet_names:
        return pd.DataFrame()
    conf_name = _pick_best_sheet(sheet_names)
    raw = _read_excel_safe(BytesIO(data), sheet_name=conf_name, header=None)
    if raw.empty:
        return pd.DataFrame()
    hrow = _find_header_row(raw)
    header = raw.iloc[hrow].tolist()
    body = raw.iloc[hrow + 1:].reset_index(drop=True)
    body.columns = header
    body = body.loc[:, body.columns.notna()]
    return body


@st.cache_data(show_spinner=False)
def _read_log_sheet(data: bytes, keyword: str) -> pd.DataFrame:
    """키워드 매칭되는 단일 로그 시트(viewing_log / sales_log)만 로딩."""
    sheet_names = _get_sheet_names(data)
    matched = None
    for name in sheet_names:
        if keyword in str(name).lower():
            matched = name
            break
    if matched is None:
        return pd.DataFrame()
    df = _read_excel_safe(BytesIO(data), sheet_name=matched, header=0)
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
    df = df.loc[:, df.columns.notna()]
    if "month" in df.columns:
        df["month"] = df["month"].apply(_to_month_timestamp)
    return df


def _read_all_sheets(data: bytes) -> dict:
    """기존 호환: 세 시트 모두 dict 로 반환. 각 시트는 별도 캐시."""
    return {
        "confidential": _read_confidential_sheet(data),
        "viewing_log": _read_log_sheet(data, "viewing"),
        "sales_log": _read_log_sheet(data, "sales_log"),
    }


def _read_content_sheet(data: bytes) -> pd.DataFrame:
    """Confidential 시트 반환 (기존 호환). 가벼운 단독 로더 위임."""
    return _read_confidential_sheet(data)


@st.cache_data(show_spinner=False)
def _viewing_log_total_by_month(data: bytes) -> dict:
    """플랫폼 전체 월별 시청분수 (콘텐츠 무관). {Timestamp: minutes}.

    파일당 1번만 계산되어 모든 콘텐츠 추정에서 공유 (가장 무거운 groupby).
    """
    vl = _read_log_sheet(data, "viewing")
    if vl.empty or "month" not in vl.columns or "watch_minutes" not in vl.columns:
        return {}
    s = vl.groupby("month")["watch_minutes"].sum()
    return {idx: float(v) for idx, v in s.items() if pd.notna(v)}


@st.cache_data(show_spinner=False)
def _sales_log_by_type_month(data: bytes, bill_type: str) -> dict:
    """매출종류별 월 총매출. {Timestamp: total}. 매출종류 변경 전까진 캐시 히트."""
    sl = _read_log_sheet(data, "sales_log")
    if sl.empty or "type" not in sl.columns or "total" not in sl.columns:
        return {}
    s = sl[sl["type"] == bill_type].groupby("month")["total"].sum()
    return {idx: float(v) for idx, v in s.items() if pd.notna(v)}


@st.cache_data(show_spinner=False)
def _content_watch_minutes_by_month(data: bytes, content_id: str) -> dict:
    """콘텐츠 월별 시청분수 (해당 콘텐츠의 최빈 category 기준). {Timestamp: minutes}.

    콘텐츠당 1번만 계산. 요율/매출종류 변경에도 캐시 유지.
    """
    vl = _read_log_sheet(data, "viewing")
    if vl.empty or "content_id" not in vl.columns:
        return {}

    try:
        cid_int = int(float(content_id))
    except (ValueError, TypeError):
        cid_int = None

    if cid_int is not None:
        rows = vl[vl["content_id"] == cid_int]
    else:
        rows = vl[vl["content_id"].astype(str) == str(content_id)]
    if rows.empty:
        return {}

    mode_series = rows["category"].dropna().mode()
    if mode_series.empty:
        return {}
    category = mode_series.iloc[0]

    s = rows[rows["category"] == category].groupby("month")["watch_minutes"].sum()
    return {idx: float(v) for idx, v in s.items() if pd.notna(v)}


@st.cache_data(show_spinner=False)
def _estimated_factor_monthly(
    data: bytes, content_id: str, bill_type: str, year: int,
) -> dict:
    """요율 미적용 월별 추정 factor. {1: factor, 2: factor, ...}.

    factor = (콘텐츠 월 시청분수 / 플랫폼 월 시청분수) × 매출종류 월 총매출
    실제 추정 정산금 = factor × 요율.
    요율 변경 시 캐시 히트되어 재계산 없음.
    """
    result = {m: float("nan") for m in range(1, 13)}
    denom = _viewing_log_total_by_month(data)
    if not denom:
        return result
    sales = _sales_log_by_type_month(data, bill_type)
    if not sales:
        return result
    numer = _content_watch_minutes_by_month(data, content_id)
    if not numer:
        return result

    for mnum in range(1, 13):
        month = pd.Timestamp(f"{year}-{mnum:02d}-01")
        n = numer.get(month, 0) or 0
        d = denom.get(month, 0) or 0
        s = sales.get(month, 0) or 0
        if d > 0 and s > 0:
            result[mnum] = (n / d) * s
    return result


def compute_estimated_monthly(
    data: bytes,
    content_id: str,
    bill_type: str,
    rate: float,
    year: int,
) -> dict:
    """매직시트 공식 월별 추정 정산금. factor × rate.

    무거운 점유율/매출 합산은 _estimated_factor_monthly 가 캐시.
    이 함수는 캐시된 factor 에 요율만 곱하므로 요율 슬라이더 변경에 거의 즉시 반응.
    """
    factor = _estimated_factor_monthly(data, content_id, bill_type, year)
    return {
        m: (f * rate if pd.notna(f) else float("nan"))
        for m, f in factor.items()
    }


@st.cache_data(show_spinner=False)
def _sales_log_type_column(data: bytes) -> pd.Series:
    """sales_log 의 type 컬럼만 단독 로드. usecols 로 1개 컬럼만 읽어 매우 가벼움."""
    sheet_names = _get_sheet_names(data)
    matched = next((n for n in sheet_names if "sales_log" in str(n).lower()), None)
    if matched is None:
        return pd.Series([], dtype=str)
    try:
        df = _read_excel_safe(
            BytesIO(data), sheet_name=matched, usecols=["type"], dtype=str,
        )
    except Exception:
        # type 컬럼이 없거나 엔진/스키마 불일치면 fallback (전체 읽기)
        try:
            full = _read_log_sheet(data, "sales_log")
            return full.get("type", pd.Series([], dtype=str))
        except Exception:
            return pd.Series([], dtype=str)
    return df.get("type", pd.Series([], dtype=str))


@st.cache_data(show_spinner=False)
def extract_sales_log_types(file_datas: list) -> list:
    """모든 업로드 파일의 sales_log 에서 매출 종류(type) 유니크 값 수집.

    sales_log 의 'type' 컬럼만 단독 로딩 → viewing_log 회피 + 다른 컬럼 회피 (가장 가벼움).
    """
    types: set = set()
    for _, data in file_datas:
        s = _sales_log_type_column(data)
        if s.empty:
            continue
        cleaned = s.dropna().astype(str).str.strip()
        cleaned = cleaned[(cleaned != "") & (~cleaned.str.lower().isin({"nan", "none"}))]
        types.update(cleaned.unique())
    return sorted(types)


# --------------------------------------------------------------------------
# 매출 종류 추출 (사이드바 필터용)
# --------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def extract_all_contents(file_datas: list[tuple[str, bytes]]) -> list[dict]:
    """업로드된 파일에서 모든 콘텐츠(id, title) 목록 수집.

    - type 필터 걸지 않음 → 정산금 미세팅 콘텐츠도 목록에 포함 (선택 가능하게)
    - 같은 ID가 여러 행에 나오면 제목 있는 행을 우선 채택 (보통 type=시청분수 행에 title 있음)
    """
    seen: dict[str, str] = {}
    for _, data in file_datas:
        try:
            df = _read_content_sheet(data)
        except Exception:
            continue
        if df.empty:
            continue
        cols = list(df.columns)
        id_col = _find_column(cols, ID_COLUMN_CANDIDATES)
        title_col = _find_column(cols, TITLE_COLUMN_CANDIDATES)
        if id_col is None:
            continue

        # 벡터화: iterrows 대신 컬럼 단위 처리
        ids = df[id_col].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
        valid = ids.notna() & (ids != "") & (~ids.str.lower().isin({"nan", "none"}))
        if title_col is not None:
            titles = df[title_col].where(df[title_col].notna(), "").astype(str).str.strip()
        else:
            titles = pd.Series([""] * len(df), index=df.index)

        ids_v = ids[valid].tolist()
        titles_v = titles[valid].tolist()
        for cid, title in zip(ids_v, titles_v):
            if cid not in seen or (not seen[cid] and title):
                seen[cid] = title
    result = [{"id": cid, "title": t} for cid, t in seen.items()]
    result.sort(key=lambda r: (r["title"] == "", r["title"].lower(), r["id"]))
    return result


def _format_content_option(c: dict) -> str:
    return f"{c['title']} ({c['id']})" if c["title"] else c["id"]


@st.cache_data(show_spinner=False)
def extract_sales_categories(file_datas: list[tuple[str, bytes]]) -> list[str]:
    """업로드된 파일들의 '정산금(rs기준)' 행 중 매출 종류 유니크 값 수집."""
    categories: set[str] = set()
    for _, data in file_datas:
        try:
            df = _read_content_sheet(data)
        except Exception:
            continue
        if df.empty:
            continue
        cols = list(df.columns)
        type_col = _find_column(cols, TYPE_COLUMN_CANDIDATES)
        cat_col = _find_column(cols, SALES_CATEGORY_COLUMN_CANDIDATES)
        if type_col is None or cat_col is None:
            continue
        mask = df[type_col].astype(str).str.strip() == REVENUE_TYPE_VALUE
        for v in df.loc[mask, cat_col].dropna().astype(str).str.strip().unique():
            if v and v.lower() not in {"nan", "none"}:
                categories.add(v)
    return sorted(categories)


# --------------------------------------------------------------------------
# 메인 데이터 로딩
# --------------------------------------------------------------------------

def load_sales_from_uploads(
    file_datas: list[tuple[str, bytes]],
    content_ids: list[str],
    selected_categories: list[str] | None = None,
    estimate_missing: bool = False,
    estimate_bill_type: str = "B-1",
    estimate_rates: dict[str, float] | None = None,
    default_rate: float = 0.5,
) -> tuple[pd.DataFrame, dict[str, str], dict[int, str]]:
    """업로드 엑셀에서 선택 콘텐츠의 월별 매출 long format 반환.

    - 기본: Confidential 시트의 type=정산금(rs기준) 행에서 실제 매출 집계
    - estimate_missing=True: 정산금 행이 없는 (콘텐츠, 연도) 조합에 대해
      viewing_log + sales_log 기반 매직시트 공식으로 추정
      반환 df 의 is_estimate 컬럼에 True 표시됨
    - estimate_rates: 콘텐츠 ID → 요율 매핑. 없으면 default_rate 사용.
    """
    if estimate_rates is None:
        estimate_rates = {}
    ids_normalized = {str(x).strip() for x in content_ids if str(x).strip()}
    empty = pd.DataFrame(columns=["content_id", "content_title", "year", "month", "revenue", "is_estimate"])
    if not ids_normalized or not file_datas:
        return empty, {}, {}

    try:
        col_override = st.secrets.get("columns", {})
    except Exception:
        col_override = {}
    id_col_override = col_override.get("content_id")
    title_col_override = col_override.get("content_title")

    rows: list = []  # DataFrame 또는 dict 들의 혼합. 마지막에 concat.
    file_status: dict[str, str] = {}
    errors: dict[int, str] = {}
    # (content_id, year) 별로 실제 정산금 데이터가 있었는지 추적 → 추정 필요 판단
    actual_ids_by_year: dict = {}
    # 추정용: 파일별 전체 시트 데이터 보관 (연도 기반 추정 시 viewing_log/sales_log 필요)
    sheets_by_year: dict = {}
    title_by_id: dict = {}

    # 모든 업로드 파일의 알려진 (id, title) 을 미리 보강.
    # 어느 연도 파일에는 정산금 행이 없어도 title 은 있을 수 있으므로, 추정 row 도 제목이 채워짐.
    try:
        for c in extract_all_contents(file_datas):
            if c.get("title") and c["id"] not in title_by_id:
                title_by_id[c["id"]] = c["title"]
    except Exception:
        pass

    for filename, data in file_datas:
        year = _detect_year_from_filename(filename)
        if year is None:
            file_status[filename] = "⚠️ 파일명에서 연도 감지 실패 (2020~2026 숫자 필요)"
            continue

        try:
            df = _read_content_sheet(data)
        except Exception as e:
            errors[year] = f"엑셀 파싱 실패: {e}"
            file_status[filename] = f"❌ 읽기 실패 ({year}년)"
            continue

        if df.empty:
            errors[year] = "시트가 비어있습니다."
            file_status[filename] = f"⚠️ 빈 시트 ({year}년)"
            continue

        cols = list(df.columns)
        id_col = id_col_override if id_col_override in cols else _find_column(cols, ID_COLUMN_CANDIDATES)
        title_col = title_col_override if title_col_override in cols else _find_column(cols, TITLE_COLUMN_CANDIDATES)
        type_col = _find_column(cols, TYPE_COLUMN_CANDIDATES)
        cat_col = _find_column(cols, SALES_CATEGORY_COLUMN_CANDIDATES)
        month_cols = _find_month_columns(cols)

        if id_col is None:
            errors[year] = f"콘텐츠 ID 컬럼을 찾지 못함. 실제: {cols}"
            file_status[filename] = f"❌ ID 컬럼 없음 ({year}년)"
            continue
        if month_cols is None:
            errors[year] = f"월별 컬럼(1~12) 을 찾지 못함. 실제: {cols}"
            file_status[filename] = f"❌ 월 컬럼 없음 ({year}년)"
            continue

        working = df.copy()
        if type_col is not None:
            working = working[working[type_col].astype(str).str.strip() == REVENUE_TYPE_VALUE]

        if selected_categories and cat_col is not None:
            working = working[working[cat_col].astype(str).str.strip().isin(selected_categories)]

        working["_id_str"] = working[id_col].astype(str).str.strip()
        # 숫자 id 가 "3338924.0" 처럼 저장되어 있을 수 있으니 소수점 제거
        working["_id_str"] = working["_id_str"].str.replace(r"\.0$", "", regex=True)
        filtered = working[working["_id_str"].isin(ids_normalized)]

        matched_rows = len(filtered)
        year_actual_ids: set = set(filtered["_id_str"].unique())
        actual_ids_by_year[year] = year_actual_ids

        if matched_rows > 0:
            # title 컬럼 정리 (벡터)
            if title_col and title_col in filtered.columns:
                title_series = filtered[title_col].where(filtered[title_col].notna(), "").astype(str).str.strip()
            else:
                title_series = pd.Series([""] * matched_rows, index=filtered.index)

            # title_by_id 보강 (id 별 첫 비어있지 않은 title)
            tdf = pd.DataFrame({"cid": filtered["_id_str"].values, "title": title_series.values})
            valid_titles = tdf[tdf["title"] != ""].drop_duplicates("cid")
            for cid, title in zip(valid_titles["cid"], valid_titles["title"]):
                if cid not in title_by_id:
                    title_by_id[cid] = title

            # 12개월 컬럼을 melt 로 long format 으로 한 번에 변환 (iterrows 제거)
            sub = filtered[["_id_str"] + month_cols].copy()
            sub.columns = ["content_id"] + list(range(1, 13))
            sub["__title"] = title_series.values
            melted = sub.melt(
                id_vars=["content_id", "__title"],
                value_vars=list(range(1, 13)),
                var_name="month",
                value_name="revenue",
            )
            # 벡터화 _to_number: string 변환 → 숫자 외 문자 제거 → to_numeric
            rev_str = (
                melted["revenue"].astype("string")
                .str.replace(r"[^0-9.\-]", "", regex=True)
            )
            rev_str = rev_str.where(rev_str.str.len() > 0)
            rev_str = rev_str.where(~rev_str.isin({"-", "."}))
            melted["revenue"] = pd.to_numeric(rev_str, errors="coerce")
            melted["content_title"] = melted["__title"]
            melted["year"] = year
            melted["is_estimate"] = False
            rows.append(
                melted[["content_id", "content_title", "year", "month", "revenue", "is_estimate"]]
            )

        # 추정용: 연도별 raw bytes 만 보관 (viewing_log/sales_log 는 캐시된 헬퍼가 lazy 로 처리)
        if estimate_missing:
            sheets_by_year[year] = data

        # 콘텐츠 제목은 Confidential 전체에서도 수집 (매칭 안 된 ID 용) — 벡터화
        if title_col:
            ids_all = df[id_col].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
            titles_all = df[title_col].where(df[title_col].notna(), "").astype(str).str.strip()
            mask_all = ids_all.isin(ids_normalized) & (titles_all != "")
            for cid, t in zip(ids_all[mask_all], titles_all[mask_all]):
                title_by_id.setdefault(cid, t)

        file_status[filename] = f"✅ {year}년 · {matched_rows}개 행 매칭 (정산금 기준)"

    # 추정: (콘텐츠, 연도) 조합 중 실제 정산금 데이터 없으면 공식으로 추정
    estimate_log: list = []
    if estimate_missing:
        for year, year_data in sheets_by_year.items():
            missing_ids_for_year = ids_normalized - actual_ids_by_year.get(year, set())
            for cid in missing_ids_for_year:
                rate = estimate_rates.get(cid, default_rate)
                monthly = compute_estimated_monthly(
                    year_data, cid, estimate_bill_type, rate, year,
                )
                nonzero_count = sum(1 for v in monthly.values() if pd.notna(v) and v > 0)
                if nonzero_count == 0:
                    continue
                title = title_by_id.get(cid, "")
                est_df = pd.DataFrame({
                    "content_id": cid,
                    "content_title": title,
                    "year": year,
                    "month": list(range(1, 13)),
                    "revenue": [monthly[m] for m in range(1, 13)],
                    "is_estimate": True,
                })
                rows.append(est_df)
                estimate_log.append(f"{year}년 · {cid}({title or 'ID'}) · {nonzero_count}개월 추정 (요율 {rate})")

        if estimate_log:
            file_status["_추정"] = f"💡 추정 계산 {len(estimate_log)}건 (매출종류={estimate_bill_type}, 콘텐츠별 요율 적용)"

    df_out = pd.concat(rows, ignore_index=True) if rows else empty.copy()
    # 빈 content_title 을 title_by_id 로 보강 (추정 row 등 제목이 누락된 경우 대응)
    if not df_out.empty and "content_title" in df_out.columns:
        empty_mask = (
            df_out["content_title"].isna()
            | df_out["content_title"].astype(str).str.strip().eq("")
        )
        if empty_mask.any():
            df_out.loc[empty_mask, "content_title"] = (
                df_out.loc[empty_mask, "content_id"].map(title_by_id).fillna("")
            )
    return df_out, file_status, errors


# --------------------------------------------------------------------------
# 렌더링
# --------------------------------------------------------------------------

def render_pivot(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("매출 데이터가 없습니다.")
        return
    pivot = df.pivot_table(
        index="year", columns="month", values="revenue", aggfunc="sum",
    ).reindex(columns=range(1, 13))
    pivot.columns = [f"{m}월" for m in pivot.columns]
    pivot["연간 합계"] = pivot.sum(axis=1, skipna=True)
    pivot["연간 평균"] = pivot.iloc[:, :12].mean(axis=1, skipna=True)

    # 마지막 행에 총합계 (월별 합 / 연간 합계 합 / 전체 월 평균)
    total_row = pivot.iloc[:, :12].sum(axis=0, skipna=True)
    total_row["연간 합계"] = pivot["연간 합계"].sum(skipna=True)
    total_row["연간 평균"] = pivot.iloc[:, :12].stack().mean()
    pivot.loc["총합"] = total_row

    st.dataframe(
        pivot.style.format("{:,.0f}", na_rep="-"),
        use_container_width=True,
    )


def render_yearly_summary(df: pd.DataFrame) -> None:
    if df.empty:
        return
    yearly = (
        df.groupby("year")["revenue"]
        .agg(total="sum", avg="mean")
        .reset_index()
        .sort_values("year")
    )
    grand_total = float(yearly["total"].sum())
    grand_avg = float(df["revenue"].mean()) if df["revenue"].notna().any() else 0.0

    cols = st.columns(len(yearly) + 1)
    for col, (_, row) in zip(cols[:-1], yearly.iterrows()):
        with col:
            st.metric(
                label=f"{int(row['year'])} 합계",
                value=f"{row['total']:,.0f}",
                delta=f"월평균 {row['avg']:,.0f}",
                delta_color="off",
            )
    with cols[-1]:
        st.metric(
            label="🏁 전체 합계",
            value=f"{grand_total:,.0f}",
            delta=f"월평균 {grand_avg:,.0f}",
            delta_color="off",
        )


def _content_labels(df: pd.DataFrame, ordered_ids: list[str]) -> dict[str, str]:
    """콘텐츠ID → "제목 (ID)" 형태의 표시용 라벨 사전.

    df 에서 빈/NaN content_title 은 건너뛰고, 비어있지 않은 첫 title 을 채택한다.
    (추정 row 가 첫 row 에 와서 title 이 비어 있어도 다른 row 의 title 을 활용)
    """
    labels = {}
    for cid in ordered_ids:
        title = ""
        if not df.empty and "content_title" in df.columns:
            sub = df[df["content_id"] == cid]
            cleaned = sub["content_title"].dropna().astype(str).str.strip()
            cleaned = cleaned[(cleaned != "") & (cleaned.str.lower() != "nan")]
            if not cleaned.empty:
                title = cleaned.iloc[0]
        labels[cid] = f"{title} ({cid})" if title and title != cid else cid
    return labels


def compute_flat_estimates(df: pd.DataFrame, ordered_ids: list[str]) -> pd.DataFrame:
    """각 콘텐츠의 FLAT 예상 금액 계산.

    - 첫 매출월 = revenue > 0 인 가장 이른 year-month
    - 그 월부터 연속 12개월 window 슬라이스 (없는 월은 NaN 처리)
    - window 내 매출 평균 (NaN 제외, 0은 포함)
    - FLAT 1년 예상 = 평균 × 12 × FLAT_DEPRECIATION (0.7)
    - FLAT 3년/5년 = FLAT 1년 × 3 / × 5
    - 계산 기간 컬럼: window 안 NaN이 아닌 월 수 (12면 정상, 미만이면 데이터 부족)
    """
    labels = _content_labels(df, ordered_ids)
    rows: list[dict] = []

    for cid in ordered_ids:
        sub = df[df["content_id"] == cid]
        # 같은 (year, month) 에 여러 매출 종류 행이 있으면 합산 → 그 달의 실제 매출
        sub = (
            sub.groupby(["year", "month"], as_index=False)["revenue"].sum(min_count=1)
            .sort_values(["year", "month"])
            .reset_index(drop=True)
        )

        nonzero = sub[sub["revenue"].notna() & (sub["revenue"] > 0)]
        if nonzero.empty:
            rows.append({
                "콘텐츠": labels[cid],
                "첫 매출월": "-",
                "첫 12개월 평균": float("nan"),
                "계산 기간(개월)": 0,
                "FLAT 1년 예상": float("nan"),
                "FLAT 3년 예상": float("nan"),
                "FLAT 5년 예상": float("nan"),
            })
            continue

        first_y = int(nonzero.iloc[0]["year"])
        first_m = int(nonzero.iloc[0]["month"])

        # 첫 매출월부터 12개월 window (연 경계 자동 처리)
        window_months = set()
        for i in range(12):
            total = (first_m - 1) + i
            y = first_y + total // 12
            m = (total % 12) + 1
            window_months.add((y, m))

        sub_keys = list(zip(sub["year"].astype(int), sub["month"].astype(int)))
        window = sub[[k in window_months for k in sub_keys]]

        avg = window["revenue"].mean()
        valid_months = int(window["revenue"].notna().sum())

        flat_1y = avg * 12 * FLAT_DEPRECIATION if pd.notna(avg) else float("nan")
        flat_3y = flat_1y * 3 if pd.notna(flat_1y) else float("nan")
        flat_5y = flat_1y * 5 if pd.notna(flat_1y) else float("nan")

        rows.append({
            "콘텐츠": labels[cid],
            "첫 매출월": f"{first_y}-{first_m:02d}",
            "첫 12개월 평균": avg,
            "계산 기간(개월)": valid_months,
            "FLAT 1년 예상": flat_1y,
            "FLAT 3년 예상": flat_3y,
            "FLAT 5년 예상": flat_5y,
        })

    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def _load_sales_cached(
    file_datas_tuple: tuple,
    content_ids_tuple: tuple,
    selected_categories_tuple: tuple,
    estimate_missing: bool,
    estimate_bill_type: str,
    estimate_rates_tuple: tuple,
    default_rate: float,
):
    """rerun 마다 같은 입력이면 즉시 캐시 히트.

    rate 만 바뀌어도 무거운 시트 파싱은 내부 캐시 (_read_*_sheet) 가 처리,
    이 wrapper 는 매칭·melt·concat 까지 한 번에 캐시.
    """
    return load_sales_from_uploads(
        list(file_datas_tuple),
        list(content_ids_tuple),
        selected_categories=list(selected_categories_tuple) or None,
        estimate_missing=estimate_missing,
        estimate_bill_type=estimate_bill_type,
        estimate_rates=dict(estimate_rates_tuple),
        default_rate=default_rate,
    )


_NUM_FORMAT_THOUSANDS = "#,##0"


def _apply_thousands_format(worksheet, *, has_index: bool) -> None:
    """워크시트의 모든 숫자 셀에 천단위 구분기호 표시 형식 적용.
    문자열·날짜 등은 isinstance 체크로 자동 skip.
    """
    min_col = 2 if has_index else 1  # 헤더 1행 / 인덱스 1열 점유 가정
    for row in worksheet.iter_rows(min_row=2, min_col=min_col):
        for cell in row:
            if isinstance(cell.value, (int, float)) and not isinstance(cell.value, bool):
                cell.number_format = _NUM_FORMAT_THOUSANDS


def build_excel_export(df: pd.DataFrame, ordered_ids: list[str]) -> bytes:
    """현재 조회 결과를 다중 시트 엑셀로 직렬화."""
    labels = _content_labels(df, ordered_ids)
    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        # 1) 월별 상세 (연-월 × 콘텐츠)
        df2 = df.copy()
        df2["period"] = (
            df2["year"].astype(str) + "-" + df2["month"].astype(str).str.zfill(2)
        )
        monthly = (
            df2.groupby(["period", "content_id"])["revenue"].sum()
            .unstack("content_id").reindex(columns=ordered_ids).sort_index()
        )
        monthly.columns = [labels[c] for c in monthly.columns]
        monthly.index.name = "연-월"
        monthly.to_excel(writer, sheet_name="월별 상세")
        _apply_thousands_format(writer.sheets["월별 상세"], has_index=True)

        # 2) 연간 합계
        yearly = (
            df.groupby(["year", "content_id"])["revenue"].sum()
            .unstack("content_id").reindex(columns=ordered_ids).sort_index()
        )
        yearly.columns = [labels[c] for c in yearly.columns]
        yearly.index.name = "연도"
        yearly.to_excel(writer, sheet_name="연간 합계")
        _apply_thousands_format(writer.sheets["연간 합계"], has_index=True)

        # 3) FLAT 예상
        compute_flat_estimates(df, ordered_ids).to_excel(
            writer, sheet_name="FLAT 예상", index=False,
        )
        _apply_thousands_format(writer.sheets["FLAT 예상"], has_index=False)

        # 4) 콘텐츠별 피벗 — 시트 하나당 한 콘텐츠 (연간 합계·평균·총합 포함)
        used_names: set[str] = set()
        for cid in ordered_ids:
            sub = df[df["content_id"] == cid]
            if sub.empty:
                continue
            piv = (
                sub.pivot_table(
                    index="year", columns="month", values="revenue", aggfunc="sum",
                )
                .reindex(columns=range(1, 13))
            )
            piv.columns = [f"{m}월" for m in piv.columns]
            piv["연간 합계"] = piv.iloc[:, :12].sum(axis=1, skipna=True)
            piv["연간 평균"] = piv.iloc[:, :12].mean(axis=1, skipna=True)

            total_row = piv.iloc[:, :12].sum(axis=0, skipna=True)
            total_row["연간 합계"] = piv["연간 합계"].sum(skipna=True)
            total_row["연간 평균"] = piv.iloc[:, :12].stack().mean()
            piv.loc["총합"] = total_row
            piv.index.name = "연도"

            # 시트명: 31자 제한 + 중복 회피 + 엑셀이 거부하는 문자 치환
            base = labels[cid]
            for ch in r"[]:*?/\\":
                base = base.replace(ch, " ")
            name = base[:28] or cid
            candidate = name
            n = 2
            while candidate in used_names:
                suffix = f" ({n})"
                candidate = name[: 28 - len(suffix)] + suffix
                n += 1
            used_names.add(candidate)
            piv.to_excel(writer, sheet_name=candidate)
            _apply_thousands_format(writer.sheets[candidate], has_index=True)

    return buffer.getvalue()


@st.cache_data(show_spinner=False)
def _build_excel_export_cached(df: pd.DataFrame, ordered_ids: tuple) -> bytes:
    """다운로드 버튼은 매 rerun 마다 data 인자를 재평가하므로 캐시."""
    return build_excel_export(df, list(ordered_ids))


def render_flat_estimates(df: pd.DataFrame, ordered_ids: list[str]) -> None:
    if df.empty:
        return
    result = compute_flat_estimates(df, ordered_ids)
    st.caption(
        f"**계산 방식**: 첫 매출월부터 연속 12개월 평균 매출 × 12 × {FLAT_DEPRECIATION}(감가) "
        f"= FLAT 1년 예상. 3년·5년은 각각 1년 예상 × 3, × 5."
    )

    num_fmt = {
        "첫 12개월 평균": "{:,.0f}",
        "FLAT 1년 예상": "{:,.0f}",
        "FLAT 3년 예상": "{:,.0f}",
        "FLAT 5년 예상": "{:,.0f}",
    }
    st.dataframe(
        result.style.format(num_fmt, na_rep="-"),
        use_container_width=True,
        hide_index=True,
    )

    # 12개월 데이터 미달 콘텐츠 경고
    short = result[(result["계산 기간(개월)"] > 0) & (result["계산 기간(개월)"] < 12)]
    if not short.empty:
        names = ", ".join(short["콘텐츠"].tolist())
        st.warning(
            f"⚠️ 다음 콘텐츠는 첫 매출월부터 12개월 데이터가 부족합니다 "
            f"(가용 월만 평균해서 계산): {names}"
        )


def render_yearly_comparison(df: pd.DataFrame, ordered_ids: list[str]) -> None:
    """연간 합계(위) + 연간 평균(아래) 비교. 행=연도, 열=콘텐츠."""
    if df.empty:
        return
    labels = _content_labels(df, ordered_ids)

    pivot_sum = (
        df.groupby(["year", "content_id"])["revenue"].sum().unstack("content_id")
        .reindex(columns=ordered_ids).sort_index()
    )
    pivot_sum.columns = [labels[c] for c in pivot_sum.columns]
    pivot_sum.index.name = "연도"

    st.caption("연간 합계 (원)")
    st.dataframe(pivot_sum.style.format("{:,.0f}", na_rep="-"), use_container_width=True)


def render_monthly_comparison(df: pd.DataFrame, ordered_ids: list[str]) -> None:
    """월별 상세 비교. 행=연-월, 열=콘텐츠."""
    if df.empty:
        return
    labels = _content_labels(df, ordered_ids)

    df2 = df.copy()
    df2["period"] = df2["year"].astype(str) + "-" + df2["month"].astype(str).str.zfill(2)
    pivot = (
        df2.groupby(["period", "content_id"])["revenue"].sum().unstack("content_id")
        .reindex(columns=ordered_ids).sort_index()
    )
    pivot.columns = [labels[c] for c in pivot.columns]
    pivot.index.name = "연-월"

    st.dataframe(
        pivot.style.format("{:,.0f}", na_rep="-"),
        use_container_width=True,
        height=400,
    )


def render_comparison_chart(df: pd.DataFrame) -> None:
    if df.empty:
        return
    plot_df = (
        df.groupby(["content_id", "year", "month"], as_index=False)["revenue"].sum()
    )
    plot_df["date"] = pd.to_datetime(
        plot_df["year"].astype(str) + "-" + plot_df["month"].astype(str).str.zfill(2) + "-01"
    )
    plot_df = plot_df.sort_values(["content_id", "date"]).reset_index(drop=True)

    fig = go.Figure()
    # 귀여운 라이트 톤: 핑크 메인 + 민트·버터 보조
    palette = ["#FF3D7F", "#7AC7E0", "#FFD580"]
    chart_labels = _content_labels(df, list(plot_df["content_id"].unique()))

    for idx, (cid, group) in enumerate(plot_df.groupby("content_id")):
        label = chart_labels.get(cid, cid)
        color = palette[idx % len(palette)]
        fig.add_trace(go.Scatter(
            x=group["date"],
            y=group["revenue"],
            mode="lines+markers",
            name=label,
            line=dict(color=color, width=2),
            marker=dict(size=5),
            hovertemplate="%{x|%Y-%m} · %{y:,.0f}<extra></extra>",
        ))
        group = group.assign(prev=group["revenue"].shift(1))
        group["pct_change"] = (group["revenue"] - group["prev"]) / group["prev"]
        drops = group[group["pct_change"] <= -0.30].dropna(subset=["revenue"])
        if not drops.empty:
            fig.add_trace(go.Scatter(
                x=drops["date"],
                y=drops["revenue"],
                mode="markers",
                name=f"{label} · 급락(-30%↓)",
                marker=dict(color="red", size=11, symbol="x", line=dict(width=2)),
                hovertemplate=(
                    "%{x|%Y-%m}<br>매출 %{y:,.0f}<br>"
                    "전월 대비 %{customdata:.0%}<extra></extra>"
                ),
                customdata=drops["pct_change"],
                showlegend=True,
            ))

    # 차트 위 보조 설명: Plotly title 대신 st.caption 으로 분리 → 버튼과 안 겹침
    st.caption("빨간 X = 전월 대비 30%↓  ·  드래그로 영역 확대 · 더블클릭으로 리셋")

    fig.update_layout(
        title=None,
        xaxis_title="",
        yaxis_title="",
        hovermode="x unified",
        height=560,
        legend=dict(
            orientation="h", yanchor="bottom", y=-0.45,
            font=dict(color="#1A1A1A", family=_PLOTLY_FONT_FAMILY),
        ),
        dragmode="zoom",
        # 라이트 톤 (원복) + 액센트만 핑크 유지
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FAFAFA",
        font=dict(color="#1A1A1A", family=_PLOTLY_FONT_FAMILY),
        margin=dict(l=20, r=20, t=80, b=20),
    )
    fig.update_xaxes(
        rangeselector=dict(
            buttons=[
                dict(count=6, label="6개월", step="month", stepmode="backward"),
                dict(count=1, label="1년", step="year", stepmode="backward"),
                dict(count=2, label="2년", step="year", stepmode="backward"),
                dict(count=3, label="3년", step="year", stepmode="backward"),
                dict(step="all", label="전체"),
            ],
            x=0, y=1.0, xanchor="left", yanchor="bottom",
            bgcolor="#F0F0F0",
            activecolor="#FF3D7F",
            font=dict(color="#1A1A1A", size=12, family=_PLOTLY_FONT_FAMILY),
        ),
        rangeslider=dict(visible=True, thickness=0.06, bgcolor="#F5F5F5"),
        type="date",
        gridcolor="#ECECEC",
        zerolinecolor="#ECECEC",
    )
    fig.update_yaxes(gridcolor="#ECECEC", zerolinecolor="#ECECEC")
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "scrollZoom": True,
            "displaylogo": False,
            "modeBarButtonsToAdd": ["drawline", "drawopenpath", "eraseshape"],
        },
    )


# --------------------------------------------------------------------------
# 메인
# --------------------------------------------------------------------------

def main() -> None:
    require_password()

    _render_title("SVOD 콘텐츠 매출 분석")
    st.caption("왓챠 '콘텐츠 매직시트' 엑셀 파일 업로드 → 콘텐츠 ID 1~3개 + 매출 종류 선택 → 연도별·월별 매출 비교")

    if "file_datas" not in st.session_state:
        st.session_state["file_datas"] = []  # list[(filename, bytes)]

    with st.sidebar:
        st.header("1. 엑셀 파일 업로드")
        files = st.file_uploader(
            "연도별 콘텐츠 매직시트 (.xlsx)",
            type=["xlsx"],
            accept_multiple_files=True,
            help="파일명에 연도(예: 2025)가 포함되어야 합니다.",
        )
        if files:
            st.session_state["file_datas"] = [(f.name, f.getvalue()) for f in files]

        file_datas = st.session_state["file_datas"]

        if file_datas:
            detected = []
            unknown = []
            for fname, _ in file_datas:
                y = _detect_year_from_filename(fname)
                if y:
                    detected.append(y)
                else:
                    unknown.append(fname)
            detected.sort()
            if detected:
                st.success(f"📅 감지된 연도: {', '.join(str(y) for y in detected)}")
            if unknown:
                st.warning(f"⚠️ 연도 감지 실패: {', '.join(unknown)}")

        st.divider()
        st.header("2. 매출 종류 필터")
        selected_categories: list[str] = []
        if file_datas:
            with st.spinner("매출 종류 추출 중..."):
                available_cats = extract_sales_categories(file_datas)
            if available_cats:
                selected_categories = st.multiselect(
                    "포함할 매출 종류 (미선택 = 전체)",
                    options=available_cats,
                    default=available_cats,
                    help="예: B-1, B-2, B-3J ...",
                )
            else:
                st.caption("매출 종류를 찾지 못했습니다.")
        else:
            st.caption("먼저 파일을 업로드하세요.")

        st.divider()
        st.header("3. 추정 매출 옵션")
        st.caption(
            "정산금이 미세팅된 콘텐츠/연도는 매직시트 공식으로 자동 추정됩니다. "
            "콘텐츠별 요율은 조회 후 결과 화면에서 따로 조정할 수 있어요."
        )
        estimate_bill_type = "B-1"
        default_rate = 0.5
        if file_datas:
            with st.spinner("sales_log 매출 종류 추출 중..."):
                bill_types = extract_sales_log_types(file_datas)
            if bill_types:
                default_idx = bill_types.index("B-1") if "B-1" in bill_types else 0
                estimate_bill_type = st.selectbox(
                    "추정 매출 종류",
                    options=bill_types,
                    index=default_idx,
                    help="정산금 미세팅 콘텐츠에 적용할 매출 종류 (예: B-1).",
                )
            else:
                st.caption("sales_log 에서 매출 종류를 찾지 못함")
        default_rate = st.number_input(
            "기본 요율 (신규 콘텐츠 초기값)",
            min_value=0.0, max_value=10.0, value=0.5, step=0.1,
            format="%.2f",
            help="콘텐츠를 새로 선택하면 이 값이 초기 요율로 들어갑니다. "
                 "조회 후 결과 페이지에서 콘텐츠별로 따로 조정할 수 있습니다.",
        )

        st.divider()
        st.header("4. 콘텐츠 선택")
        content_ids: list[str] = []
        if file_datas:
            with st.spinner("콘텐츠 목록 불러오는 중..."):
                all_contents = extract_all_contents(file_datas)
            if all_contents:
                options = [_format_content_option(c) for c in all_contents]
                option_to_id = {_format_content_option(c): c["id"] for c in all_contents}
                selected = st.multiselect(
                    f"콘텐츠 선택 (최대 3개 · 총 {len(all_contents):,}개에서 제목/ID 검색)",
                    options=options,
                    max_selections=3,
                    placeholder="제목 또는 콘텐츠 ID 입력 후 선택",
                )
                content_ids = [option_to_id[s] for s in selected]
            else:
                st.caption("콘텐츠 목록을 추출하지 못했습니다.")
        else:
            st.caption("먼저 파일을 업로드하세요.")

        run = st.button("조회", type="primary", use_container_width=True)

    if not st.session_state["file_datas"]:
        st.info("👈 먼저 왼쪽 사이드바에서 **엑셀 파일을 업로드** 하세요.")
        return

    # 조회 버튼이 눌리면 query 스냅샷을 세션에 저장.
    # 이후 요율 변경에 의한 rerun 에서도 같은 query 로 재계산.
    if run:
        if not content_ids:
            st.warning("콘텐츠를 1개 이상 선택해주세요.")
            return
        st.session_state["query"] = {
            "content_ids": content_ids,
            "selected_categories": selected_categories,
            "estimate_bill_type": estimate_bill_type,
            "default_rate": default_rate,
        }

    q = st.session_state.get("query")
    if not q:
        st.info("👈 콘텐츠를 선택하고 **조회** 를 눌러주세요.")
        return

    # 콘텐츠 라벨 맵 (요율 에디터에서 제목 표시용)
    label_map: dict[str, str] = {}
    if st.session_state["file_datas"]:
        for c in extract_all_contents(st.session_state["file_datas"]):
            label_map[c["id"]] = f"{c['title']} ({c['id']})" if c["title"] else c["id"]

    # 콘텐츠별 요율 에디터 — 항상 노출.
    # 정산금 미세팅 콘텐츠/연도에만 실제로 적용됨 (실제 정산금 있는 곳은 그 값 그대로).
    rates: dict[str, float] = {}
    if q["content_ids"]:
        st.subheader("⚙️ 콘텐츠별 요율 설정")
        st.caption(
            f"매출 종류 **{q['estimate_bill_type']}** 기준으로 콘텐츠별 요율을 따로 설정할 수 있습니다. "
            "정산금이 미세팅된 콘텐츠/연도에만 적용되며, 실제 정산금이 있는 부분은 시트의 값을 그대로 사용합니다. "
            "값을 바꾸면 아래 결과가 자동으로 다시 계산됩니다."
        )
        rate_cols = st.columns(min(3, len(q["content_ids"])))
        for col, cid in zip(rate_cols, q["content_ids"]):
            with col:
                widget_key = f"rate_{cid}"
                # 초기값: 이미 위젯에 값이 있으면 그대로, 없으면 query 시점의 default_rate
                initial = st.session_state.get(widget_key, q["default_rate"])
                rates[cid] = st.number_input(
                    f"📺 {label_map.get(cid, cid)}",
                    min_value=0.0, max_value=10.0,
                    value=float(initial), step=0.1, format="%.2f",
                    key=widget_key,
                )
        st.divider()

    with st.spinner("엑셀 파일 분석 중..."):
        df, file_status, errors = _load_sales_cached(
            tuple(st.session_state["file_datas"]),
            tuple(q["content_ids"]),
            tuple(q["selected_categories"] or ()),
            True,
            q["estimate_bill_type"],
            tuple(sorted(rates.items())),
            q["default_rate"],
        )

    with st.expander(f"📁 파일 처리 현황 ({len(file_status)}개)", expanded=False):
        for name, status in file_status.items():
            st.write(f"- **{name}**: {status}")

    if errors:
        with st.expander(f"⚠️ 로드 경고 ({len(errors)}건)", expanded=True):
            for y, msg in errors.items():
                st.write(f"- **{y}년**: {msg}")

    if df.empty:
        st.warning(
            "선택한 콘텐츠에 **매출 데이터가 없습니다.**\n\n"
            "아래 중 하나에 해당할 수 있어요:\n"
            "- 매직시트의 `Confidential` 시트에 `type=정산금(rs기준)` 행이 아직 세팅되지 않은 콘텐츠 "
            "(매출 종류·요율 입력 전)\n"
            f"- 선택한 매출 종류 필터에 해당 콘텐츠의 매출이 포함되지 않음 "
            f"(사이드바 '2. 매출 종류 필터' 를 전체로 바꿔서 재조회 해보세요)"
        )
        return

    found_ids = df["content_id"].unique().tolist()
    missing = [cid for cid in q["content_ids"] if cid not in found_ids]
    if missing:
        st.warning(f"다음 ID는 어느 파일에서도 찾지 못했습니다: {', '.join(missing)}")

    # 비교 대상 콘텐츠 요약 + 엑셀 다운로드 버튼 (한 줄)
    labels = _content_labels(df, found_ids)
    summary_col, download_col = st.columns([4, 1])
    with summary_col:
        st.markdown(
            "**비교 콘텐츠:** "
            + "  ·  ".join(f"📺 {labels[cid]}" for cid in found_ids)
        )
    with download_col:
        try:
            excel_bytes = _build_excel_export_cached(df, tuple(found_ids))
            st.download_button(
                "📥 엑셀 다운로드",
                data=excel_bytes,
                file_name=(
                    f"watcha_svod_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx"
                ),
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                use_container_width=True,
            )
        except Exception as exc:  # pragma: no cover - 안전망
            st.caption(f"⚠️ 엑셀 생성 실패: {exc}")

    # 추정치 포함 여부 배너 (콘텐츠별 요율 표시)
    if "is_estimate" in df.columns and df["is_estimate"].any():
        estimated_pairs = df[df["is_estimate"]].groupby("content_id")["year"].unique()
        parts = []
        for cid, years in estimated_pairs.items():
            yr_txt = ", ".join(str(int(y)) for y in sorted(years))
            applied_rate = rates.get(cid, q["default_rate"])
            parts.append(f"**{labels.get(cid, cid)}** · 요율 `{applied_rate:.2f}` · ({yr_txt})")
        st.info(
            "💡 아래 데이터에 **추정치**가 포함되어 있습니다 "
            f"(매출종류 `{q['estimate_bill_type']}` 가정): "
            + " / ".join(parts)
        )
    st.divider()

    # 1) 시간 추이 라인 차트 (비주얼 비교 먼저)
    st.subheader("📈 매출 추이 비교")
    render_comparison_chart(df)

    # 2) FLAT 예상 금액
    st.subheader("💰 FLAT 예상 금액")
    render_flat_estimates(df, found_ids)

    # 3) 연간 합계 비교 테이블
    st.subheader("📋 연간 합계 비교")
    render_yearly_comparison(df, found_ids)

    # 3) 월별 상세 비교 테이블
    st.subheader("📋 월별 상세 비교")
    st.caption("전체 기간의 연-월 × 콘텐츠 매출 (스크롤 가능)")
    render_monthly_comparison(df, found_ids)

    # 4) 콘텐츠별 상세 피벗 (기본 접힘)
    st.divider()
    st.subheader("🔍 콘텐츠별 상세")
    for cid in found_ids:
        sub = df[df["content_id"] == cid]
        with st.expander(f"📺 {labels[cid]}", expanded=False):
            render_yearly_summary(sub)
            st.caption("연도 × 월 매출")
            render_pivot(sub)


if __name__ == "__main__":
    main()
