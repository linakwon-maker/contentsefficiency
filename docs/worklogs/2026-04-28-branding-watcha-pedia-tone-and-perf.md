# 2026-04-28 · 브랜딩(WATCHA SVOD) · 왓챠피디아 라이트 톤 · 엑셀 파싱 성능 · 빌드 안정화

> **작성 목적**: 다음 세션에서 이 프로젝트를 이어 작업할 때 빠르게 맥락을 복구할 수 있도록 오늘 한 변경(8커밋, app.py +331줄, +이미지/테마/요구 파일 등)의 **왜 / 무엇 / 어떻게** 와 다음 후보까지 정리. 코드는 git 에서 볼 수 있으니 **숨은 결정**과 **재발 방지** 중심.
>
> 이전 워크로그: `2026-04-23-mvp-launch.md` (MVP), `2026-04-27-rate-editor-perf-ux-polish.md` (요율 에디터·추정 성능·UX). 이 문서는 그 후속.

---

## 0. TL;DR — 오늘 추가된 8개 커밋 한 줄 요약

| 해시 | 메시지 | 핵심 |
|------|--------|------|
| `b44ad50` | feat: 제목을 'WATCHA SVOD 콘텐츠 매출 분석'으로 변경 + 왓챠 W 로고 추가 | 페이지 타이틀·아이콘·`st.logo` + `_render_title` 헬퍼 도입. 임시 SVG W. |
| `ea5febe` | fix: 왓챠 공식 W 아이콘으로 교체 (Square 변형, png+svg) | `~/Downloads/WATCHA_Icon` 의 공식 PNG/SVG 로 교체. 앱은 PNG 기본. |
| `3846f5d` | style: 제목과 W 로고를 한 줄로 밀착 배치 + 이모지 제거 | columns 분리 → flexbox + base64 inline img, gap 14px, 🔒/📊 제거. |
| `eb9567e` | style: 왓챠피디아 톤 다크 테마 적용 | `.streamlit/config.toml` 다크 base + 광범위 글로벌 CSS + Plotly 다크. |
| `c4fea9b` | style: 라이트 테마로 전환 (흰톤 배경 + 다크 차콜 텍스트) | 사용자 요구로 dark→light 반전. 액센트(#FF0558)는 유지. |
| `0aa4595` | perf: 엑셀 파싱 속도 대폭 개선 (calamine 엔진 + 컬럼 부분 로딩 + iterrows 제거) | calamine 엔진 + `usecols=["type"]` + `load_sales_from_uploads` 의 melt 벡터화. |
| `ae6821a` | fix: Streamlit Cloud 빌드 안정화 - calamine 의존성 옵션 + 엔진 fallback 강화 | calamine 강제 설치 제거 + `_read_excel_safe` / `_excel_file_safe` wrapper. |
| `c48a43d` | fix(chart): 매출 추이 차트 상단 텍스트와 rangeselector 버튼 겹침 해결 | Plotly 내부 title 제거 → st.caption 분리, 셀렉터 y=1.0, top margin 80. |

세션 결과: app.py 1,200줄 → 1,452줄 (+252). 새 파일: `.streamlit/config.toml`, `assets/watcha_w.png`, `assets/watcha_w.svg`.

---

## 1. 컨텍스트 — 이 세션이 시작될 때 상태

### 1.1. 배경
사용자가 또 "저번 작업 이어서 할게" 로 시작. 메모리(`~/.claude/projects/-Users-linazzang/memory/`) 가 비어있어 이전 세션 transcript jsonl 을 직접 파싱해 흐름을 복구. 마지막 커밋이 워크로그 자체(`d8620aa`) 였고, 워크로그 내부의 **13절 권장 첫 단계** 와 **12절 다음 후보**가 사실상 다음 세션의 시작점이라는 사실을 확인. 이번 세션 초반에 메모리 시스템에 다음 세 파일을 저장 → 다음부터 jsonl 파싱 없이 즉시 컨텍스트 진입 가능:
- `MEMORY.md` (인덱스)
- `project_contentsefficiency.md` (프로젝트 사실 + 워크로그 인계 패턴)
- `feedback_work_style.md` (간결 지시 = 명시 승인, 변경→commit→push 한 사이클)

### 1.2. 환경 복원 시 주의 (어제 워크로그 9.1 기준)
- **gh CLI 가 `/tmp/gh-bin` 에 사라져있었음** (재부팅 추정). 오늘 다시 깔았음. 단, **첫 시도에 디렉터리로 만들어 놓고 `cp gh /tmp/gh-bin/gh` 처럼 배치하는 실수**를 함 — `~/.gitconfig` 의 credential helper 가 `/tmp/gh-bin auth git-credential` (즉 `/tmp/gh-bin` 자체를 실행파일로 가정) 이어서 push 가 `is a directory` 에러로 실패. **재발 방지**: 배치 시 반드시 `cp gh_..._/bin/gh /tmp/gh-bin && chmod +x /tmp/gh-bin` 으로 **단일 바이너리** 형태로 둘 것.
- **repo-local git config** 는 살아있었음 (`lina.kwon@watcha.com` / `Lina Kwon`).
- **로컬 venv·streamlit 등 그대로 살아있음**.
- **Streamlit 배포 앱**: HTTP 303 = 정상.

### 1.3. 시작 시점 코드 상태
어제 시점 그대로. 페이지 제목 `📊 콘텐츠 매출 분석`, 사이드바·결과 페이지 모두 디폴트 라이트 톤(Streamlit 기본). 추정 성능은 어제 캐시 분리로 슬라이더 < 1초 달성.

---

## 2. 사용자 요구 (시간 순)

이번 세션의 요구는 **브랜딩 → 톤 → 성능 → 빌드 회복 → 차트 미세조정** 순으로 진화함:

1. **타이틀 변경 + 왓챠 W 로고 삽입** → `b44ad50` (1차)
2. **공식 로고 사용 (다운로드 폴더 첨부)** → `ea5febe` (교체)
3. **로고와 타이틀이 동떨어져 보임 + 이모지 제거** → `3846f5d` (밀착)
4. **왓챠피디아 톤 (https://pedia.watcha.com/ko/contents/tEKzVJV) 참고해 꾸며줘** → `eb9567e` (다크) → `c4fea9b` (라이트로 정정)
5. **매출 종류 추출/조회 후 결과값 단계가 느림** → `0aa4595` (calamine + 벡터화)
6. **"Error running app" 으로 배포 실패** → `ae6821a` (calamine 옵션화 + safe wrapper)
7. **매출 추이 차트 상단 텍스트가 셀렉터 버튼과 겹침** → `c48a43d` (title 제거 + caption 분리)

**중요한 사용자 정정 사례**: (4)에서 본인이 링크한 페이지를 내가 "다크 시네마틱"으로 잘못 분석함. 사용자가 직접 "베이스랑 폰트 색을 서로 바꿔줘. 흰톤 배경에 다크 차콜색 폰트로. 위에 보여준 왓챠피디아 페이지도 베이스가 흰톤이잖아" 로 정정. **재발 방지**는 11.1 절.

---

## 3. 변경 1 — 브랜딩: WATCHA SVOD + 왓챠 W 로고 (`b44ad50` → `ea5febe` → `3846f5d`)

### 3.1. 최종 결과 (3846f5d 기준)
- 페이지 제목·브라우저 탭: `WATCHA SVOD 콘텐츠 매출 분석`
- 페이지 아이콘: 왓챠 공식 W (PNG)
- Streamlit `st.logo()` 좌상단 글로벌 표시 (size="large")
- 로그인 화면·메인 모두 `_render_title("WATCHA SVOD 콘텐츠 매출 분석")` 한 줄에 [로고 48px][제목] flexbox 밀착 (gap 14px)

### 3.2. 결정 사항
- **공식 SVG 보다 PNG 를 기본 자산으로 사용** — 이유: Streamlit 의 `st.image`/`st.logo` 가 SVG 의 viewBox·clip-path 를 환경에 따라 다르게 처리한 사례를 회피. PNG 는 어디서나 동일.
- **`st.image` + `st.columns` 분리 → flexbox + base64 inline img 로 변경** — st.columns 는 컬럼 사이에 자동 gutter 가 들어가 로고-제목 간격이 너무 멀었음. flex `gap:14px` 로 시각적 결속.
- **이모지(🔒, 📊) 제거** — 공식 로고가 강한 시각 표식이라 이모지가 군더더기. 로그인 화면도 동일.
- **`_LOGO_PATH` 존재 체크** — 자산 누락 시 page_icon/타이틀 헬퍼가 안전하게 fallback (📊 / 텍스트만).
- **로고에 핑크 글로우** — `box-shadow:0 2px 12px rgba(255,5,88,0.25)`. 너무 강하지 않게.

### 3.3. 코드 변경 요약
```python
# app.py 상단
from pathlib import Path
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

def _render_title(title: str, *, level: str = "h1") -> None:
    if _LOGO_PATH.exists():
        import base64
        b64 = base64.b64encode(_LOGO_PATH.read_bytes()).decode()
        st.markdown(
            f"""<div style="display:flex; align-items:center; gap:14px; margin:0 0 1rem 0;">
                <img src="data:image/png;base64,{b64}"
                     style="width:44px; height:44px; border-radius:10px;
                            box-shadow:0 2px 12px rgba(255,5,88,0.25);" />
                <{level} style="margin:0; line-height:1.1; font-weight:800;
                                 letter-spacing:-0.02em; border-left:none; padding-left:0;">
                    {title}
                </{level}>
            </div>""",
            unsafe_allow_html=True,
        )
```
- `_render_title` 의 `border-left:none; padding-left:0;` — 4절에서 추가한 글로벌 h2 좌측 핑크 액센트 바가 h1 에까지 적용되는 것을 차단하기 위함.

### 3.4. 자산 위치
- `assets/watcha_w.png` (10.5KB, Square 변형, 공식)
- `assets/watcha_w.svg` (543B, 공식)
- 둘 다 `~/Downloads/WATCHA_Icon/` 에서 복사. **PNG 가 코드의 기본 경로**, SVG 는 보존용.

---

## 4. 변경 2 — 왓챠피디아 라이트 톤 (`eb9567e` → `c4fea9b`)

### 4.1. 사용자 요구
"https://pedia.watcha.com/ko/contents/tEKzVJV 왓챠피디아의 UI를 보고 참고해서 유사한 톤으로 꾸며줄래"

### 4.2. 1차 시도 — 다크 톤 (`eb9567e`) → ❌ 잘못된 분석
WebFetch 결과만 보고 "K-streaming aesthetic = 다크 차콜" 로 단정. 실제 왓챠피디아 메인은 **라이트 베이스 + 핑크 액센트**. 사용자가 즉시 정정.

### 4.3. 2차 — 라이트 톤 (`c4fea9b`) ✅
**왓챠피디아 톤의 핵심**:
- 흰 베이스 (#FFFFFF), 살짝 오프화이트 그라데이션 (#FAFAFA)
- 다크 차콜 텍스트 (#1A1A1A)
- 왓챠 핑크 액센트 (#FF0558)
- 부드러운 보더 (#ECECEC), 카드 배경 (#F5F5F5)
- 둥근 모서리(8~14px), 넓은 여백, 미니멀

### 4.4. 적용 영역 (글로벌 CSS + Streamlit theme)

**`.streamlit/config.toml`** (신규):
```toml
[theme]
base = "light"
primaryColor = "#FF0558"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F5F5F5"
textColor = "#1A1A1A"
font = "sans serif"
```

**글로벌 CSS** (app.py 상단, `st.markdown(unsafe_allow_html=True)` 한 블록):
- `.stApp` — 흰톤 → 오프화이트 240px 그라데이션
- `.block-container` — max-width 1240px, padding-top 2rem
- `h1` — font-weight 800, letter-spacing -0.02em
- `h2` — **좌측 3px 핑크 보더 + padding-left 0.6rem** (왓챠피디아의 액센트 바 느낌). h1 에 적용 방지를 위해 `_render_title` 가 inline `border-left:none` 으로 override
- `.stCaption`, `[data-testid="stCaptionContainer"]` — muted gray (#6B6B6B)
- `hr` — #ECECEC, opacity 0.9
- 사이드바 — 살짝 더 회색 (#FAFAFA), 보더 우측, h2/h3 uppercase + letter-spacing 0.08em
- 버튼 primary — pill (border-radius 999px), 핑크 채움, hover brightness 1.08 + translateY -1px
- 버튼 secondary — pill outline (white + #ECECEC border)
- 입력 위젯 — white bg, border 1px #ECECEC, radius 10px
- `[data-testid="stMetric"]` — 카드 (#F5F5F5 + #ECECEC border, radius 14px, padding 1rem 1.2rem)
- expander — 카드처럼
- DataFrame/Table — radius 12px + border + overflow hidden
- alert — radius 12px + border
- 스크롤바 — #D4D4D4 thumb, 999px

### 4.5. Plotly 차트 톤 일치 (요점)
다크/라이트 두 번 다 차트도 같이 맞춤. 라이트 최종값:
- `paper_bgcolor="#FFFFFF"`, `plot_bgcolor="#FAFAFA"`
- `font=dict(color="#1A1A1A")`
- `gridcolor="#ECECEC"`, `zerolinecolor="#ECECEC"`
- rangeselector `bgcolor="#F0F0F0"`, `activecolor="#FF0558"`
- rangeslider `bgcolor="#F5F5F5"`
- 라인 팔레트 `["#FF0558", "#5BC0EB", "#F7B538"]` — 1번이 왓챠 핑크. (어제까지는 plotly 기본 `["#1f77b4", ...]` 이었음.)

---

## 5. 변경 3 — 엑셀 파싱 속도 대폭 개선 (`0aa4595`)

### 5.1. 문제
사용자: "매출 종류 추출, 조회 후 결과값 나오는 과정이 오래걸리네 더 빠르게 단축할 수 없니?"

어제 캐시 분리로 **요율 슬라이더 변경** 은 빠른데, **첫 조회/사이드바 첫 로딩** 은 여전히 느림. 진단 결과 두 가지 큰 병목:
1. **`pd.read_excel(engine="openpyxl")`** — openpyxl 은 파이썬 내 행-단위 파싱. 가장 느린 엔진.
2. **`load_sales_from_uploads` 의 이중 `iterrows()`** — `for row in filtered.iterrows(): for mcol in month_cols: rows.append(dict)` — 콘텐츠 행 × 12 개월 만큼 dict append. 큰 시트면 수만 회.

### 5.2. 변경 — 4단계
**1. `python-calamine` 엔진 도입** (1차에서는 requirements 강제, 6절에서 옵션화)
- `python-calamine` 은 Rust 기반 엑셀 파서. pandas 2.2+ 가 `engine="calamine"` 으로 정식 지원.
- 같은 파일 기준 보통 **5~10배 빠름**.

**2. `extract_sales_log_types` — type 컬럼만 단독 로딩**
새 헬퍼 `_sales_log_type_column(data)` 추가. `pd.read_excel(..., usecols=["type"], dtype=str)` 로 단일 컬럼만 파싱 → sales_log 의 다른 무거운 컬럼 회피. 기존 `_read_log_sheet` fallback 유지.

**3. `load_sales_from_uploads` — `iterrows` 제거 → `melt` 벡터화**
```python
sub = filtered[["_id_str"] + month_cols].copy()
sub.columns = ["content_id"] + list(range(1, 13))
sub["__title"] = title_series.values
melted = sub.melt(
    id_vars=["content_id", "__title"],
    value_vars=list(range(1, 13)),
    var_name="month",
    value_name="revenue",
)
melted["revenue"] = [_to_number(v) for v in melted["revenue"]]
melted["content_title"] = melted["__title"]
melted["year"] = year
melted["is_estimate"] = False
rows.append(melted[["content_id", "content_title", "year", "month", "revenue", "is_estimate"]])
```
- `_find_month_columns` 가 항상 정확히 12개 또는 None 만 반환하므로 `range(1,13)` 매핑이 안전.
- `_to_number` 는 list comprehension 으로 호출 — 반복문 오버헤드는 있지만 iterrows 보다 훨씬 빠름.
- `rows: list[dict]` → `rows: list` (DataFrame 또는 dict 혼합 → 마지막에 `pd.concat(rows, ignore_index=True)`).

**4. `extract_all_contents` 와 Confidential 제목 보강 루프** — `iterrows` 제거 → 컬럼 단위 처리.

### 5.3. 적용 후 효과 (관찰)
사용자 환경의 정확한 측정값은 받지 못했지만, 로컬에서 calamine 활성화 시 read_excel 자체 속도가 큰 폭으로 줄었고, melt 도 pandas 내부 C-루프로 동작하므로 **첫 조회의 결과 표시까지 시간이 가시적으로 감소**할 것으로 기대. (어제와 마찬가지로 슬라이더 reactivity 는 별도 캐시로 그대로 빠름.)

---

## 6. 변경 4 — Streamlit Cloud 빌드 안정화 (`ae6821a`)

### 6.1. 사고
`0aa4595` push 직후 사용자 보고: "Error running app. If you need help, try the Streamlit docs and forums."

### 6.2. 진단
로컬에서는 HTTP 200 정상. → 환경 차이. 의심 포인트:
1. `requirements.txt` 의 `python-calamine>=0.2` 가 Streamlit Cloud pip 단계에서 설치 실패해 의존성 통째로 깨짐, 또는
2. pandas 의 `engine="calamine"` 호출이 클라우드 환경에서 다른 예외를 raise — 일부 read_excel 호출이 단일 try/except 가 아니라 그냥 죽음.

### 6.3. 해결 — 두 단 fallback
**(a) `python-calamine` 을 강제 의존성에서 제거**:
```
# python-calamine: 옵션. 있으면 read_excel 이 5~10배 빨라짐. 없어도 openpyxl 로 fallback.
# Streamlit Cloud 환경에서 자동 설치 실패 사례가 있어 강제 의존성에서 제외.
```
설치돼 있으면 자동 사용, 없으면 openpyxl 로 동작.

**(b) `_PRIMARY_ENGINE` + safe wrapper 도입**:
```python
_PRIMARY_ENGINE = "openpyxl"
try:
    import python_calamine  # noqa
    _PRIMARY_ENGINE = "calamine"
except Exception:
    pass

def _read_excel_safe(*args, **kwargs):
    try:
        return pd.read_excel(*args, engine=_PRIMARY_ENGINE, **kwargs)
    except Exception:
        if _PRIMARY_ENGINE == "openpyxl":
            raise
        return pd.read_excel(*args, engine="openpyxl", **kwargs)

def _excel_file_safe(data: bytes) -> pd.ExcelFile:
    ...  # 동일 패턴
```
모든 `pd.read_excel` / `pd.ExcelFile` 호출을 이 wrapper 경유로 변경. **어떤 단계에서 calamine 이 실패하든 openpyxl 로 자동 재시도** → 절대 죽지 않음.

### 6.4. 결과
사용자 확인: "배포는 잘 됐어". 즉, calamine 설치 실패가 진짜 원인인지, 단순히 wrapper 추가가 안정화 시킨 건지 명확히 구분되진 않지만 **현재 클라우드 환경은 안정**.

---

## 7. 변경 5 — 매출 추이 차트 상단 겹침 해결 (`c48a43d`)

### 7.1. 문제 (스크린샷)
`📈 매출 추이 비교` (h2 섹션 헤딩) 바로 아래에:
- Plotly **내부 title** "콘텐츠 매출 추이 비교 · 빨간 X = 전월 대비 30%↓ · 드래그 확대 · 더블클릭 리셋" 가 좌측 상단에 그려지고
- 같은 영역에 **rangeselector 버튼** (`6개월 1년 2년 3년 전체`) 이 y=1.08 위치로 오버레이 → 텍스트끼리 겹침

### 7.2. 결정
**Plotly 내부 title 제거**. 섹션 h2 가 이미 같은 정보를 전달하므로 중복. 보조 설명(빨간 X / 드래그 / 더블클릭) 은 차트 위 `st.caption` 로 분리.

### 7.3. 코드 변경
```python
st.caption("빨간 X = 전월 대비 30%↓  ·  드래그로 영역 확대 · 더블클릭으로 리셋")

fig.update_layout(
    title=None,
    ...
    margin=dict(l=20, r=20, t=80, b=20),  # 70 → 80
)
fig.update_xaxes(
    rangeselector=dict(
        ...,
        x=0, y=1.0,  # 1.08 → 1.0 (plot 영역 바로 위)
        xanchor="left", yanchor="bottom",
        ...
        font=dict(color="#1A1A1A", size=12),
    ),
    ...
)
```

### 7.4. 주의
- 차후 `_render_title` 같은 헬퍼로 차트 상단에 Plotly title 을 다시 넣을 일이 있다면 **st.caption 과 둘 중 하나만**. 동시에 두면 다시 겹침.
- rangeselector 위치 변경 시 `top margin` 도 같이 조정. 셀렉터를 더 위로 올리면 margin 도 늘려야 안 잘림.

---

## 8. 코드 구조 변경 (어제 대비 핵심)

```
app.py (1452줄, 어제 1200줄 대비 +252)
├── (L1-50)   import (Path 추가)
├── (L52-80)  ★ _LOGO_PATH 정의 + set_page_config + st.logo + 글로벌 CSS 블록
├── (L80-105) ★ _render_title(title, level="h1") — base64 inline 로고 + flexbox
├── (L107-)  require_password() — 로그인 화면도 _render_title 사용
├── (L)      유틸 (_normalize / _find_column / _extract_month / _to_number / ...)
├── (L399-)  ★ 엑셀 엔진 결정 + safe wrapper (커밋 ae6821a)
│   ├── _PRIMARY_ENGINE = "openpyxl" 또는 "calamine"
│   ├── _read_excel_safe(*args, **kwargs)   ← 모든 read_excel 의 단일 통로
│   ├── _excel_file_safe(data)              ← 모든 ExcelFile 의 단일 통로
│   ├── _get_sheet_names(data)              ← _excel_file_safe 위임
│   ├── _read_confidential_sheet(data)      ← _read_excel_safe 사용
│   ├── _read_log_sheet(data, keyword)      ← _read_excel_safe 사용
│   └── _read_all_sheets(data)              ← dict 래퍼
├── (L)      추정 (어제와 동일 — _viewing_log_total_by_month / _sales_log_by_type_month / _content_watch_minutes_by_month / _estimated_factor_monthly / compute_estimated_monthly)
├── (L591-)  ★ _sales_log_type_column(data) — sales_log 의 type 컬럼만 usecols 로 단독 로드
├── (L)      extract_sales_log_types — _sales_log_type_column 사용 + set 벡터화
├── (L)      extract_all_contents — iterrows 제거 → 컬럼 단위 valid mask + zip
├── (L)      extract_sales_categories — 어제와 동일
├── (L)      load_sales_from_uploads
│   ├── rows: list (DataFrame + dict 혼합 → 마지막에 pd.concat)
│   ├── 메인 매칭 루프: filtered → melt 로 long format 한 번에 변환
│   ├── title_by_id 보강도 벡터화
│   └── 추정 row 도 12 dict append → 1 DataFrame
├── (L1106-) ★ render_comparison_chart
│   ├── st.caption 으로 보조 설명 분리
│   ├── Plotly title=None
│   ├── rangeselector y=1.0, font size=12, activecolor=#FF0558
│   ├── paper #FFF, plot #FAFAFA, grid #ECECEC
│   └── palette: ["#FF0558", "#5BC0EB", "#F7B538"]
└── main() — _render_title 사용, 본문 구성은 어제와 동일
```

### 새 / 변경된 파일
- `assets/watcha_w.png` — 공식 Square (10.5KB)
- `assets/watcha_w.svg` — 공식 SVG (543B)
- `.streamlit/config.toml` — 라이트 테마 + #FF0558 primary
- `requirements.txt` — `python-calamine` 라인은 주석 처리(옵션)
- 어제부터 있던 `.streamlit/secrets.toml` 은 .gitignore 로 보호

### 중요한 코드 규약 (어제 기준 + 보강)
- **모든 read_excel 호출은 `_read_excel_safe` 경유**. 직접 `pd.read_excel(... engine=...)` 부르지 말 것 — fallback 우회.
- **모든 ExcelFile 호출은 `_excel_file_safe` 경유**.
- **공식 자산은 `assets/` 에**. 컴포넌트가 자산 경로를 직접 참조 가능 (Path(__file__).parent / "assets" / ...).
- **이모지는 섹션 헤딩(`📈`, `💰`, `📋`, `🔍` 등)에는 유지, 메인/로그인 타이틀에는 사용하지 않음**. 이유: 공식 W 로고가 강한 시각 표식이라 충돌.
- **글로벌 CSS 의 `h2` 좌측 핑크 보더는 모든 h2 에 적용됨** — h1 에 같은 효과를 원하지 않으면 `_render_title` 처럼 inline `border-left:none` override.
- **Plotly title 과 rangeselector 는 같은 위쪽 영역 공유** — 둘 중 하나만 쓰거나, top margin 으로 충분히 떼어놓기.
- **calamine 활성화 여부는 `_PRIMARY_ENGINE` 한 곳**. 로그·디버그 시 이 변수 확인.

---

## 9. 배포·인증·git 운영 메모

### 9.1. 인증 상태
- gh CLI v2.91.0 을 **`/tmp/gh-bin` (단일 바이너리)** 로 재설치. **디렉터리 형태로 만들지 말 것** (1.2 절 참조). credential helper 는 `!/tmp/gh-bin auth git-credential` 그대로.
- `~/.config/gh/hosts.yml` 에 토큰 살아있음 → `gh auth status` 즉시 OK.
- repo-local `user.email = lina.kwon@watcha.com`, `user.name = Lina Kwon` 유지.

### 9.2. 배포 흐름
- `git push origin main` → Streamlit Cloud webhook 자동 재배포 (보통 1~3분).
- `requirements.txt` 가 변경되면 의존성 재설치까지 발생 → 재배포 시간이 평소보다 길어짐. **이번처럼 새 패키지(`python-calamine`)를 강제로 추가하면 클라우드 환경에서 설치 실패 시 앱이 통째로 죽을 수 있음** — 의심스러우면 옵션화 + safe wrapper.

### 9.3. force-push / amend 사례
이번 세션엔 없음. 모두 일반 fast-forward push.

---

## 10. 사용자 스타일 추가 관찰 (어제 10절 보강)

- **공식 자산 / 외부 레퍼런스를 직접 첨부**. 로고는 다운로드 폴더 경로로, 톤 레퍼런스는 URL 로. 추측보다 정답 자료 제공 → 미스매치 즉시 정정.
- **"이상해", "동떨어진 느낌이야" 같은 직관적 부정 표현이 즉각 신호**. 정밀한 어떤 픽셀이 어떻다는 설명 없음. 즉시 다음 시도로.
- **테마 같이 큰 변경에도 반복 1~2 사이클로 합의**. (다크 → 라이트 → OK)
- **성능 민감도 높음**. "빠르게 할 수 있니" 가 자주 오는 요구. 데이터 정확성·UI 명확성과 동급 우선순위.
- **에러는 그대로 짧게 알려줌**. "Error running app 라고 뜨네" — 스크린샷이나 로그 없이도 즉시 진단 가능한 정도의 정보. 응답도 짧게 + 해결 액션.

---

## 11. 디버깅·재발 방지 메모 (어제 11절 보강)

### 11.1. 톤·UX 분석 시 — 자기 추측 검증
- WebFetch 의 분석 결과를 그대로 채용하지 말 것. **레퍼런스 페이지 자체의 실제 화면을 사용자가 보고 있음** — 분석이 틀리면 즉시 사용자가 정정한다.
- 다크/라이트 같은 큰 결정은 **렌더링된 결과를 먼저 보여주고 confirmation 받기** 가 더 빠를 수 있음. 하지만 이 사용자는 이미 결과를 보고 즉시 피드백 주는 흐름이라, 1차 시도 후 빠르게 정정도 OK.

### 11.2. 빌드 깨졌을 때
- 로컬 `streamlit run app.py --server.headless=true --server.port=XXXX` + `curl localhost:XXXX` 로 HTTP 200 확인이 1차 진단.
- 로컬은 살아있고 클라우드만 죽으면 **의심 1순위는 `requirements.txt` 변경** + **2순위는 클라우드 시크릿/환경변수 의존**.
- 새 라이브러리 도입 시 **try/except import + fallback 경로**를 항상 같이 둘 것.

### 11.3. Plotly 차트 레이아웃
- title 과 rangeselector / annotations / legend 가 **같은 paper 영역(>1.0 y) 공유**. 좌측 정렬 텍스트끼리 겹치는 사례 흔함.
- 셀렉터 위치 변경 시 `top margin` 동시 조정. y=1.0 ≈ plot 상단 경계, y=1.08 ≈ title 영역.

### 11.4. base64 inline image 의 함정
- `_render_title` 가 매 호출마다 base64 인코딩 → CPU 거의 없지만 캐시는 안 됨. 원하면 모듈 레벨에서 한 번 인코딩하고 재사용. (지금은 한 페이지에 1~2번 호출이라 무시해도 됨.)
- `<img src="data:image/png;base64,...">` 은 `st.image` 보다 레이아웃 컨트롤 자유로움.

### 11.5. flexbox + Streamlit
- Streamlit 내 `st.markdown(..., unsafe_allow_html=True)` 로 flex 컨테이너 만들 때, **자식 요소가 한 줄 안에 들어가야 함**. h1/h2/h3 는 기본 `display:block` + `margin` 이 있어 inline override 필요 (`margin:0; line-height:1.1`).

### 11.6. ★ 새 라이브러리 도입은 **옵션 + fallback** 패턴
calamine 케이스가 그대로 적용. 새 의존성을 추가할 땐:
1. requirements.txt 에 강제로 넣기 전 **try-import + 사용처 wrapper** 먼저
2. 로컬에서만이 아니라 **Streamlit Cloud 환경(linux x86_64, 그들 파이썬 버전)** 에서 휠 가용성 확인
3. 핵심 기능이 그 라이브러리에 의존한다면 정말 강제, 아니면 옵션

### 11.7. 자산 경로
- `Path(__file__).parent / "assets" / ...` 패턴. 프로젝트 루트에서 streamlit run 해야 함. 다른 디렉터리에서 실행하면 깨질 수 있음 — 단, Streamlit Cloud 는 항상 repo 루트.

---

## 12. 다음 세션을 위한 후보 (어제 12절 갱신)

**어제 12절 후보 중 남아있는 것** (변동 없음):
- [ ] 2020~2024 파일 실제 테스트 — `_to_month_timestamp` 다양한 월 표기
- [ ] 추정치 시각 구분 — 라인 점선·표 셀 음영. `is_estimate` 컬럼 이미 있음
- [ ] FLAT 예상 금액에 추정치 포함 표시
- [ ] bill_name ↔ type 매핑 테이블
- [ ] 추정 요율 자동 추천 (다른 매출종류 / 유사 콘텐츠 평균)
- [ ] viewing_log 시청분수 트렌드 별도 뷰
- [ ] 요율 일괄 적용 버튼 ("선택 콘텐츠 모두 0.5")
- [ ] 요율 프리셋 저장/복원
- [ ] 결과 엑셀 다운로드 버튼
- [ ] 콘텐츠 비교 4개+ 지원 (현재 max 3)
- [ ] 차트 "급락 임계값(-30%)" 사이드바 노출

**이번 세션에서 새로 떠오른 후보**:
- [ ] **calamine 휠 가용 여부 확인 후 optional dep 활성화** — Streamlit Cloud 가 정말로 calamine 설치를 거부하는지, pyproject 추가하면 되는지 확인. 확인되면 requirements 에 다시 넣어 첫 조회 시간을 한층 더 단축.
- [ ] **`_to_number` 자체 벡터화** — 지금 `[_to_number(v) for v in melted["revenue"]]` 는 list-comp. pandas `to_numeric(errors="coerce")` + 정규식 정리 한 번에 처리 가능 → 큰 시트에서 의미 있는 추가 가속.
- [ ] **viewing_log 콘텐츠별 시청분수 인덱싱 통합** — 현재 `_content_watch_minutes_by_month` 가 콘텐츠당 viewing_log 를 다시 필터링. `_viewing_log_indexed(data) → {(cid, category): pd.Series}` 같은 인덱스 캐시 추가하면 콘텐츠 N 개 비교에서 viewing_log 처리 1회로 끝.
- [ ] **차트 줌 시 한국어 fonts 깨짐 여부** — 라이트 톤 적용 후 Plotly 한글 폰트 확인. 필요 시 `font=dict(family="Pretendard, ...")` 명시.
- [ ] **다크 모드 토글** — 사용자 환경(브라우저 다크 모드)에 따라 자동 전환. `prefers-color-scheme` 미디어 쿼리 + 두 셋 변수.
- [ ] **로딩 스피너/진행 상태** — 첫 조회 동안 어떤 단계인지 (시트 파싱 / 추정 계산 / 차트 렌더) 표시. perf 자체는 빠르더라도 체감 개선.

---

## 13. 다음 세션 시작 시 권장 첫 단계

1. **이 문서 + 어제(`2026-04-27-rate-editor-perf-ux-polish.md`) + MVP(`2026-04-23-mvp-launch.md`) 모두 훑기**.
2. `git log --oneline -20` 로 새 커밋 확인.
3. **메모리 인덱스 확인**: `cat ~/.claude/projects/-Users-linazzang/memory/MEMORY.md` — 이번 세션부터 자동 적재 시작.
4. **gh CLI 살아있는지** `ls -la /tmp/gh-bin` (디렉터리 아닌 단일 바이너리여야 함). 없으면 9.1·1.2 절 절차로 재설치.
5. **repo-local git config**: `git config --get user.email` → `lina.kwon@watcha.com` 인지.
6. **로컬 환경 복원** 필요하면 `cd /Users/linazzang/Projects/contentsefficiency && .venv/bin/streamlit run app.py`.
7. **배포 앱** https://watcha-content-efficiency.streamlit.app 살아있는지 (HTTP 303 = 정상).
8. **calamine 활성화 여부** 확인: 앱 코드의 `_PRIMARY_ENGINE` 가 무엇인지 — Streamlit Cloud 환경에서 import 성공하는지가 클라우드 측 `_PRIMARY_ENGINE` 값을 결정. 로컬은 0.4.0 설치되어 있어 calamine.
9. 사용자에게 12절 후보 검토 요청. 보통 사용자는 본인 우선순위를 가지고 옴.

---

## 14. 부록 — 이번 세션의 사용자 메시지 흐름 (요약)

- "저번 작업 이어서 할게" → 메모리 비어있어 jsonl 파싱으로 컨텍스트 복원, 메모리 시드 작성, 환경 점검(gh 사라짐 / git config OK / 배포 OK / venv OK), 12절 후보 표 제시
- "새 요구 사항: 콘텐츠 매출 분석 제목 부분에 [WATCHA SVOD 콘텐츠 매출 분석]으로 바꾸고 왓챠 W 로고도 넣어줘" → b44ad50
- "아니야 저 로고는 이상해. 공식 로고를 써줘 [Image #2]" → ea5febe
- "로고랑 타이틀이 너무 동떨어져 있는 느낌이야 이모지는 지우고 WATCHA SVOD 콘텐츠 매출 분석만 남겨줘" → 3846f5d
- "https://pedia.watcha.com/ko/contents/tEKzVJV 왓챠피디아의 UI를 보고 참고해서 유사한 톤으로 꾸며줄래" → eb9567e (다크 — 잘못)
- "베이스라랑 폰트 색을 서로 바꿔줘. 흰톤 배경에 다크 차콜색 폰트로. 위에 보여준 왓챠피디아 페이지도 베이스가 흰톤이잖아" → c4fea9b
- "매출 종류 추출, 조회 후 결과값 나오는 과정이 오래걸리네 더 빠르게 단축할 수 없니?" → 0aa4595 (calamine + melt 벡터화 + usecols)
- "Error running app. If you need help, try the Streamlit docs and forums. 라고 뜨네" → ae6821a (옵션화 + safe wrapper)
- "배포는 잘 됐어 [Image #3] 매출 추이 비교 부분 텍스트 위치 안 겹쳐지게 조정해줘" → c48a43d (Plotly title 제거 + caption 분리)
- "워크로그 작성하자. ..." → 본 문서

각 요청마다 **추가 컨텍스트 질문 없이 즉시 구현·푸시**가 표준 패턴이었음 (어제와 동일). 사용자 정정도 짧은 한 줄에 의도가 분명하게 들어감.
