"""왓챠 콘텐츠 매출 분석 MVP (엑셀 업로드 버전).

연도별 '콘텐츠 매직시트' 엑셀 파일(최대 7개, 2020~2026)을 업로드하고
콘텐츠 ID 1~3개 + 매출 종류 필터를 지정하면 2020~2026 월별 매출을
피벗 테이블 / 연간 요약 / 비교 라인 차트 / 급락 지점으로 보여준다.
"""

from __future__ import annotations

import re
from io import BytesIO
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

st.set_page_config(
    page_title="콘텐츠 매출 분석",
    page_icon="📊",
    layout="wide",
)


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

    st.title("🔒 콘텐츠 매출 분석")
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


@st.cache_data(show_spinner=False)
def _read_all_sheets(data: bytes) -> dict:
    """엑셀에서 confidential / viewing_log / sales_log 시트를 한 번에 읽기."""
    xls = pd.ExcelFile(BytesIO(data), engine="openpyxl")
    out: dict = {}

    # Confidential 시트 (헤더 자동 감지)
    conf_name = _pick_best_sheet(xls.sheet_names)
    raw = pd.read_excel(xls, sheet_name=conf_name, header=None)
    if not raw.empty:
        hrow = _find_header_row(raw)
        header = raw.iloc[hrow].tolist()
        body = raw.iloc[hrow + 1:].reset_index(drop=True)
        body.columns = header
        body = body.loc[:, body.columns.notna()]
        out["confidential"] = body
    else:
        out["confidential"] = pd.DataFrame()

    # viewing_log & sales_log (header=0 형식)
    for key, keyword in [("viewing_log", "viewing"), ("sales_log", "sales_log")]:
        matched = None
        for name in xls.sheet_names:
            if keyword in str(name).lower():
                matched = name
                break
        if matched:
            df = pd.read_excel(xls, sheet_name=matched, header=0)
            df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
            df = df.loc[:, df.columns.notna()]
            if "month" in df.columns:
                df["month"] = df["month"].apply(_to_month_timestamp)
            out[key] = df
        else:
            out[key] = pd.DataFrame()

    return out


@st.cache_data(show_spinner=False)
def _read_content_sheet(data: bytes) -> pd.DataFrame:
    """Confidential 시트만 반환 (기존 호환)."""
    return _read_all_sheets(data).get("confidential", pd.DataFrame())


def compute_estimated_monthly(
    viewing_log: pd.DataFrame,
    sales_log: pd.DataFrame,
    content_id: str,
    bill_type: str,
    rate: float,
    year: int,
) -> dict:
    """매직시트 공식으로 월별 추정 정산금 계산.

    정산금 = (해당 콘텐츠·category·월의 watch_minutes / 플랫폼 전체 월 watch_minutes)
             × (해당 매출종류의 월 sales_log total)
             × 요율

    - category: viewing_log 에서 해당 콘텐츠의 최빈 category (보통 'm'=영화 / 't'=TV)
    - 반환: {1: 추정액, 2: 추정액, ...} (값 없으면 NaN)
    """
    result = {m: float("nan") for m in range(1, 13)}
    if viewing_log.empty or sales_log.empty:
        return result

    # content_id 매칭 (int/str 유연)
    try:
        cid_int = int(float(content_id))
    except (ValueError, TypeError):
        cid_int = None

    if cid_int is not None and "content_id" in viewing_log.columns:
        content_rows = viewing_log[viewing_log["content_id"] == cid_int]
    else:
        content_rows = viewing_log[viewing_log["content_id"].astype(str) == str(content_id)]

    if content_rows.empty:
        return result

    mode_series = content_rows["category"].dropna().mode()
    if mode_series.empty:
        return result
    category = mode_series.iloc[0]

    # 월별 플랫폼 전체 시청분수 (분모는 month 기준만, category 무관)
    denom_by_month = viewing_log.groupby("month")["watch_minutes"].sum()
    # 매출종류/월 별 sales_log 매출
    sales_filtered = sales_log[sales_log["type"] == bill_type]
    sales_by_month = sales_filtered.groupby("month")["total"].sum()

    content_filtered = content_rows[content_rows["category"] == category]
    numer_by_month = content_filtered.groupby("month")["watch_minutes"].sum()

    for mnum in range(1, 13):
        month = pd.Timestamp(f"{year}-{mnum:02d}-01")
        numer = float(numer_by_month.get(month, 0) or 0)
        denom = float(denom_by_month.get(month, 0) or 0)
        sales_val = float(sales_by_month.get(month, 0) or 0)
        if denom > 0 and sales_val > 0:
            result[mnum] = (numer / denom) * sales_val * rate

    return result


@st.cache_data(show_spinner=False)
def extract_sales_log_types(file_datas: list) -> list:
    """모든 업로드 파일의 sales_log 에서 매출 종류(type) 유니크 값 수집."""
    types: set = set()
    for _, data in file_datas:
        try:
            sheets = _read_all_sheets(data)
        except Exception:
            continue
        sl = sheets.get("sales_log", pd.DataFrame())
        if sl.empty or "type" not in sl.columns:
            continue
        for v in sl["type"].dropna().astype(str).str.strip().unique():
            if v and v.lower() not in {"nan", "none"}:
                types.add(v)
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
        for _, row in df.iterrows():
            cid = str(row[id_col]).strip()
            cid = re.sub(r"\.0$", "", cid)
            if not cid or cid.lower() in {"nan", "none", ""}:
                continue
            title = ""
            if title_col is not None:
                tval = row[title_col]
                if tval is not None and not (isinstance(tval, float) and pd.isna(tval)):
                    title = str(tval).strip()
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
    estimate_rate: float = 0.5,
) -> tuple[pd.DataFrame, dict[str, str], dict[int, str]]:
    """업로드 엑셀에서 선택 콘텐츠의 월별 매출 long format 반환.

    - 기본: Confidential 시트의 type=정산금(rs기준) 행에서 실제 매출 집계
    - estimate_missing=True: 정산금 행이 없는 (콘텐츠, 연도) 조합에 대해
      viewing_log + sales_log 기반 매직시트 공식으로 추정
      반환 df 의 is_estimate 컬럼에 True 표시됨
    """
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

    rows: list[dict] = []
    file_status: dict[str, str] = {}
    errors: dict[int, str] = {}
    # (content_id, year) 별로 실제 정산금 데이터가 있었는지 추적 → 추정 필요 판단
    actual_ids_by_year: dict = {}
    # 추정용: 파일별 전체 시트 데이터 보관 (연도 기반 추정 시 viewing_log/sales_log 필요)
    sheets_by_year: dict = {}
    title_by_id: dict = {}

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
        year_actual_ids: set = set()
        for _, row in filtered.iterrows():
            cid = row["_id_str"]
            title = ""
            if title_col and title_col in row:
                tval = row[title_col]
                if tval is not None and not (isinstance(tval, float) and pd.isna(tval)):
                    title = str(tval).strip()
            if title and cid not in title_by_id:
                title_by_id[cid] = title
            year_actual_ids.add(cid)
            for idx, mcol in enumerate(month_cols, start=1):
                rows.append({
                    "content_id": cid,
                    "content_title": title,
                    "year": year,
                    "month": idx,
                    "revenue": _to_number(row[mcol]),
                    "is_estimate": False,
                })
        actual_ids_by_year[year] = year_actual_ids

        # 추정용 viewing_log / sales_log 확보
        if estimate_missing:
            try:
                all_sheets = _read_all_sheets(data)
                sheets_by_year[year] = {
                    "viewing_log": all_sheets.get("viewing_log", pd.DataFrame()),
                    "sales_log": all_sheets.get("sales_log", pd.DataFrame()),
                    "confidential": all_sheets.get("confidential", pd.DataFrame()),
                }
            except Exception:
                pass

        # 콘텐츠 제목은 Confidential 전체에서도 수집 (매칭 안 된 ID 용)
        if title_col:
            df["_id_str_all"] = df[id_col].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
            for _, row in df.iterrows():
                _cid = row["_id_str_all"]
                if _cid in ids_normalized and _cid not in title_by_id:
                    tval = row.get(title_col)
                    if tval is not None and not (isinstance(tval, float) and pd.isna(tval)):
                        t = str(tval).strip()
                        if t:
                            title_by_id[_cid] = t

        file_status[filename] = f"✅ {year}년 · {matched_rows}개 행 매칭 (정산금 기준)"

    # 추정: (콘텐츠, 연도) 조합 중 실제 정산금 데이터 없으면 공식으로 추정
    estimate_log: list = []
    if estimate_missing:
        for year, sheets in sheets_by_year.items():
            viewing_log = sheets.get("viewing_log", pd.DataFrame())
            sales_log = sheets.get("sales_log", pd.DataFrame())
            if viewing_log.empty or sales_log.empty:
                continue
            missing_ids_for_year = ids_normalized - actual_ids_by_year.get(year, set())
            for cid in missing_ids_for_year:
                monthly = compute_estimated_monthly(
                    viewing_log, sales_log, cid,
                    estimate_bill_type, estimate_rate, year,
                )
                nonzero_count = sum(1 for v in monthly.values() if pd.notna(v) and v > 0)
                if nonzero_count == 0:
                    continue
                title = title_by_id.get(cid, "")
                for mnum in range(1, 13):
                    rows.append({
                        "content_id": cid,
                        "content_title": title,
                        "year": year,
                        "month": mnum,
                        "revenue": monthly[mnum],
                        "is_estimate": True,
                    })
                estimate_log.append(f"{year}년 · {cid}({title or 'ID'}) · {nonzero_count}개월 추정")

        if estimate_log:
            file_status["_추정"] = f"💡 추정 계산 {len(estimate_log)}건 (매출종류={estimate_bill_type}, 요율={estimate_rate})"

    df_out = pd.DataFrame(rows)
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
    cols = st.columns(len(yearly))
    for col, (_, row) in zip(cols, yearly.iterrows()):
        with col:
            st.metric(
                label=f"{int(row['year'])} 합계",
                value=f"{row['total']:,.0f}",
                delta=f"월평균 {row['avg']:,.0f}",
                delta_color="off",
            )


def _content_labels(df: pd.DataFrame, ordered_ids: list[str]) -> dict[str, str]:
    """콘텐츠ID → "제목 (ID)" 형태의 표시용 라벨 사전."""
    labels = {}
    for cid in ordered_ids:
        sub = df[df["content_id"] == cid]
        title = sub["content_title"].iloc[0] if not sub.empty else ""
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
        df.groupby(["content_id", "content_title", "year", "month"], as_index=False)
        ["revenue"].sum()
    )
    plot_df["date"] = pd.to_datetime(
        plot_df["year"].astype(str) + "-" + plot_df["month"].astype(str).str.zfill(2) + "-01"
    )
    plot_df = plot_df.sort_values(["content_id", "date"]).reset_index(drop=True)

    fig = go.Figure()
    palette = ["#1f77b4", "#ff7f0e", "#2ca02c"]

    for idx, (cid, group) in enumerate(plot_df.groupby("content_id")):
        title = group["content_title"].iloc[0] or cid
        label = f"{title} ({cid})" if title != cid else cid
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

    fig.update_layout(
        title="콘텐츠 매출 추이 비교 (빨간 X = 전월 대비 30% 이상 하락)",
        xaxis_title="연월",
        yaxis_title="매출",
        hovermode="x unified",
        height=520,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3),
    )
    st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------------------------------
# 메인
# --------------------------------------------------------------------------

def main() -> None:
    require_password()

    st.title("📊 콘텐츠 매출 분석")
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
        st.header("3. 추정 옵션")
        estimate_missing = st.checkbox(
            "정산금 미세팅 콘텐츠 자동 추정",
            value=False,
            help="Confidential 시트에 정산금(rs기준) 행이 없는 콘텐츠를 "
                 "viewing_log + sales_log 기반으로 추정합니다. "
                 "매직시트 공식: (콘텐츠 category월 시청분수 / 월 전체 시청분수) "
                 "× 매출종류 총매출 × 요율",
        )
        estimate_bill_type = "B-1"
        estimate_rate = 0.5
        if estimate_missing:
            if file_datas:
                with st.spinner("sales_log 매출 종류 추출 중..."):
                    bill_types = extract_sales_log_types(file_datas)
                if bill_types:
                    default_idx = bill_types.index("B-1") if "B-1" in bill_types else 0
                    estimate_bill_type = st.selectbox(
                        "추정 시 적용할 매출 종류",
                        options=bill_types,
                        index=default_idx,
                    )
                else:
                    st.caption("sales_log 에서 매출 종류를 찾지 못함")
            estimate_rate = st.number_input(
                "추정 시 적용할 요율",
                min_value=0.0, max_value=10.0, value=0.5, step=0.1,
                format="%.2f",
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

    if not run:
        st.info("👈 콘텐츠를 선택하고 **조회** 를 눌러주세요.")
        return

    if not content_ids:
        st.warning("콘텐츠를 1개 이상 선택해주세요.")
        return

    with st.spinner("엑셀 파일 분석 중..."):
        df, file_status, errors = load_sales_from_uploads(
            st.session_state["file_datas"],
            content_ids,
            selected_categories=selected_categories or None,
            estimate_missing=estimate_missing,
            estimate_bill_type=estimate_bill_type,
            estimate_rate=estimate_rate,
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
    missing = [cid for cid in content_ids if cid not in found_ids]
    if missing:
        st.warning(f"다음 ID는 어느 파일에서도 찾지 못했습니다: {', '.join(missing)}")

    # 비교 대상 콘텐츠 요약 (한 줄)
    labels = _content_labels(df, found_ids)
    st.markdown(
        "**비교 콘텐츠:** "
        + "  ·  ".join(f"📺 {labels[cid]}" for cid in found_ids)
    )

    # 추정치 포함 여부 배너
    if "is_estimate" in df.columns and df["is_estimate"].any():
        estimated_pairs = df[df["is_estimate"]].groupby("content_id")["year"].unique()
        parts = []
        for cid, years in estimated_pairs.items():
            yr_txt = ", ".join(str(int(y)) for y in sorted(years))
            parts.append(f"**{labels.get(cid, cid)}** ({yr_txt})")
        st.info(
            "💡 아래 데이터에 **추정치**가 포함되어 있습니다 "
            f"(매출종류 `{estimate_bill_type}` · 요율 `{estimate_rate}` 가정): "
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
