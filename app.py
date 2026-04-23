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


@st.cache_data(show_spinner=False)
def _read_content_sheet(data: bytes) -> pd.DataFrame:
    """엑셀 bytes → Confidential 시트 + 헤더 자동 감지된 DataFrame."""
    xls = pd.ExcelFile(BytesIO(data), engine="openpyxl")
    sheet = _pick_best_sheet(xls.sheet_names)
    raw = pd.read_excel(xls, sheet_name=sheet, header=None)
    if raw.empty:
        return raw
    hrow = _find_header_row(raw)
    header = raw.iloc[hrow].tolist()
    body = raw.iloc[hrow + 1:].reset_index(drop=True)
    body.columns = header
    # 비어있는/중복 컬럼 제거
    body = body.loc[:, body.columns.notna()]
    return body


# --------------------------------------------------------------------------
# 매출 종류 추출 (사이드바 필터용)
# --------------------------------------------------------------------------

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
) -> tuple[pd.DataFrame, dict[str, str], dict[int, str]]:
    """업로드 엑셀에서 선택 콘텐츠의 월별 매출(정산금 기준) long format 반환."""
    ids_normalized = {str(x).strip() for x in content_ids if str(x).strip()}
    empty = pd.DataFrame(columns=["content_id", "content_title", "year", "month", "revenue"])
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
        for _, row in filtered.iterrows():
            cid = row["_id_str"]
            title = ""
            if title_col and title_col in row:
                tval = row[title_col]
                if tval is not None and not (isinstance(tval, float) and pd.isna(tval)):
                    title = str(tval).strip()
            for idx, mcol in enumerate(month_cols, start=1):
                rows.append({
                    "content_id": cid,
                    "content_title": title,
                    "year": year,
                    "month": idx,
                    "revenue": _to_number(row[mcol]),
                })

        file_status[filename] = f"✅ {year}년 · {matched_rows}개 행 매칭 (정산금 기준)"

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
        st.header("3. 콘텐츠 ID 입력")
        id1 = st.text_input("콘텐츠 ID 1", key="id1")
        id2 = st.text_input("콘텐츠 ID 2 (선택)", key="id2")
        id3 = st.text_input("콘텐츠 ID 3 (선택)", key="id3")
        run = st.button("조회", type="primary", use_container_width=True)

    if not st.session_state["file_datas"]:
        st.info("👈 먼저 왼쪽 사이드바에서 **엑셀 파일을 업로드** 하세요.")
        return

    if not run:
        st.info("👈 콘텐츠 ID 를 입력하고 **조회** 를 눌러주세요.")
        return

    content_ids = [x for x in [id1, id2, id3] if x.strip()]
    if not content_ids:
        st.warning("콘텐츠 ID 를 1개 이상 입력해주세요.")
        return

    with st.spinner("엑셀 파일 분석 중..."):
        df, file_status, errors = load_sales_from_uploads(
            st.session_state["file_datas"],
            content_ids,
            selected_categories=selected_categories or None,
        )

    with st.expander(f"📁 파일 처리 현황 ({len(file_status)}개)", expanded=False):
        for name, status in file_status.items():
            st.write(f"- **{name}**: {status}")

    if errors:
        with st.expander(f"⚠️ 로드 경고 ({len(errors)}건)", expanded=True):
            for y, msg in errors.items():
                st.write(f"- **{y}년**: {msg}")

    if df.empty:
        st.error(
            "입력한 콘텐츠 ID 에 해당하는 매출 데이터를 찾지 못했습니다.\n\n"
            "- 콘텐츠 ID 가 맞는지, 매출 종류 필터가 너무 좁지 않은지 확인해주세요."
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
    st.divider()

    # 1) 시간 추이 라인 차트 (비주얼 비교 먼저)
    st.subheader("📈 매출 추이 비교")
    render_comparison_chart(df)

    # 2) 연간 합계 비교 테이블
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
