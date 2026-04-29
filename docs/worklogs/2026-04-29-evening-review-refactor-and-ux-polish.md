# 2026-04-29 (저녁) · 코드 리뷰 ★1~7 리팩터 + 자동완성 검색 + UX 다듬기

> **작성 목적**: 같은 날(2026-04-29) 오후·저녁 두 세션 중 두 번째 세션. 오전 세션은 `2026-04-29-feature-then-font-and-multiselect-rework.md` 에서 multiselect → 검색 input + 결과 button 으로 교체까지. 이 워크로그는 그 직후의 **15 커밋, app.py +247줄(1870 → 2117)** 을 정리. 흐름이 “전체 코드 리뷰 → ★1~7 일괄 적용 → 사용자 요청 UX 폴리시 ×10” 로 매우 작은 변화의 연속이라 그룹별로 묶어 정리.
>
> 이전 워크로그: `2026-04-23`, `2026-04-27`, `2026-04-28`, `2026-04-29-feature-then-font-and-multiselect-rework.md`. 이 문서는 마지막의 후속.

---

## 0. TL;DR — 15 커밋 한 줄 요약 (시간순)

| # | 해시 | 메시지 | 핵심 |
|---|------|--------|------|
| 1 | `d83c255` | refactor: 코드 리뷰 ★1~★7 일괄 적용 | 사용자 요청 “Streamlit 앱 전체 리뷰” 후속. 7개 항목 한 커밋에 |
| 2 | `52c8fa4` | fix(font): expander 헤더의 ligature 텍스트 깨짐 — 셀렉터 광범위화 | 파일 처리 현황 expander 의 `_arrow_drop_down` 글자가 한글 폰트로 깨져 노출. summary 안 가능한 모든 아이콘 element 셀렉터 광범위화 + `display:none + visibility:hidden + width/height/font-size:0 + color:transparent` 다층 hide |
| 3 | `a89311e` | feat(ux): 추정 매출 종류 — B-1 기본 + 기타 토글 | 평소엔 `추정 매출 종류: **B-1** (기본)` 만 표시, 체크박스 켜면 전체 radio 펼침 |
| 4 | `abf3c4f` | ux: 기타 체크박스를 추정 매출 종류 ‘아래’로 | 시선 흐름 라벨 → 체크박스 → 펼침 |
| 5 | `8763d07` | feat(ux): 콘텐츠 검색 자동완성 (1차) | prefix > substring > 공백무시 정렬, markdown bold 하이라이트, Enter 자동 추가, 10개+더 보기 |
| 6 | `6085cec` | ux(search): Enter 자동 추가 제거 | 사용자 정정 — 자동 추가 의도와 다름. 키워드 매칭 자동 추천만 유지 |
| 7 | `63dde9d` | fix(ui): 메트릭 카드 value 폰트 자동 축소 | container query (`container-type: inline-size` + `clamp(0.85rem, 11cqw, 1.7rem)`) 로 카드 폭 비례 |
| 8 | `ae3d306` | style(metric): 라벨 연한 핑크 하이라이트 | `inline-block + padding 3px 10px + border-radius 8px` (1차) |
| 9 | `cc0eb88` | style(metric): 라벨 하이라이트 글자에 타이트 | `inline + padding 0 4px + border-radius 4px` 형광펜 스타일로 변경 |
| 10 | `a531709` | style(metric): 라벨과 숫자 사이 여백 | `margin-bottom: 0.6rem` |
| 11 | `ab8db2a` | style(chart): 급락 마커 X → ▼ | `symbol="triangle-down"`, size 13, 흰 외곽선. 캡션도 동기화 |
| 12 | `0350c15` | feat(flat): 감가 계수 number_input | 기본 0.7, 0~1 범위, step 0.05. 화면·엑셀 다운로드 모두 동일 적용 |
| 13 | `82c3646` | ux(metric): 합계 카드 한 줄 5개 grid | 6개 이상 자동 줄바꿈. 5칸 고정 columns 로 마지막 행도 너비 동일 |
| 14 | `c3981f4` | ux(metric): 전체 합계 카드 1번 위치 | items 순서 변경 |
| 15 | `a80e159` | feat: 콘텐츠 선택 최대 3 → 5개 | full 판정·hint·caption·요율 컬럼·페이지 안내 모두 동기화 |

세션 결과: app.py **1870 → 2117줄 (+247)**. 새 파일 없음. 다음 후보·UX 결정사항이 늘어남.

---

## 1. 시작 상태

- 마지막 커밋: `87850da` (오전 세션의 워크로그 자체).
- 사용자 환경:
  - macOS Chrome 추정. dropdown popover 의 옵션 글자 안 보임 = 환경 의존적 깨짐.
  - 비번 보호 배포 페이지 https://watcha-content-efficiency.streamlit.app
  - gh CLI 살아있음, repo-local git config OK.
- 코드 상태: 콘텐츠 선택은 **검색 input + 결과 버튼** 패턴. 매출 종류 multiselect / 추정 매출 종류 selectbox 는 그대로(아직 깨짐 보고 X).

---

## 2. 사용자 요구 (시간 순)

**전체 리뷰 단계** (1):
1. “Streamlit 앱 전체를 리뷰해줘. 1) 명백한 버그 2) 런타임 에러 가능성 3) 상태 관리 문제 4) 성능 병목 순으로 정리. 추측 말고 실제 코드 근거.” → 17개 항목 정리 → “1부터 7번 다 진행해줘”

**잔여 폰트 깨짐** (2):
2. “파일 처리 현황 부분에 글자가 겹쳐 보여 [파일 처리 현황]만 보이게” (스크린샷에 `_arrow_drop_down` 노출)

**UX 폴리시 연속 요청** (3~15):
3. “[추정 매출 옵션] B-1 을 기본으로 하고 나머지는 기타로 묶어서 필요할 경우에만 선택”
4. “‘기타 매출 종류에서 선택’을 ‘추정 매출 종류’ 보다 아래에 둘래”
5. “콘텐츠 검색 시 자동완성 기능이 있으면 좋을 것 같은데 구현해줘”
6. “자동 추가 말고, 검색창에 글자를 입력했을 때 해당 키워드가 들어간 타이틀들을 보여주는 식으로 자동 추천”
7. “[콘텐츠별 상세] 합계 요약 부분 숫자가 크면 ...으로 생략 — 폰트가 카드 크기에 맞춰서 조정”
8. “‘연도+합계’ 부분에 연한 핑크 하이라이트”
9. “하이라이트가 너무 뚱뚱해 글자에 맞춰서”
10. “합계 아래 한줄 띄워줘”
11. “[매출 추이 비교] 급락 표시 X 를 다른 기호로 — 추천”
12. “1순위 적용” (▼)
13. “[FLAT 예상 금액] 감가 기본 0.7, 추가로 원하는 수치로 조정”
14. “[콘텐츠별 상세] 합계 6개부터 줄 구분, 1줄 최대 5개”
15. “전체 합계가 1번으로”
16. “콘텐츠 조회 최대 5개까지 늘려줘”

**워크로그**:
17. “워크로그 작성하자.”

각 요청은 거의 즉시 코드 변경 + 푸시. 사용자가 짧은 정정으로 미세 조정(예: 핑크 하이라이트 패딩 → 타이트, 자동완성 자동추가 → 추천만).

---

## 3. 그룹별 정리

### 3.1. 코드 리뷰 ★1~7 (`d83c255`)

리뷰 결과 17개 항목(B1~B5 / R1~R10 / S1~S8 / P1~P11) 중 사용자가 선택한 ★1~7 적용:

| ★ | 항목 | 적용 내용 |
|---|---|---|
| 1 | S2/S8: query / quick selected_ids 비동기 | `_render_query_form` 진입 시 `selected_content_ids{key_suffix}` 가 미설정이면 `st.session_state["query"]["content_ids"]` 로 동기화 → quick picker 변경 후 ← 처음으로 복귀 시 일관됨 |
| 2 | B5: 매출 종류 multiselect / 추정 selectbox dropdown 깨짐 위험 | 매출 종류 multiselect → **체크박스 grid** (`st.columns + st.checkbox`, 기본 전체 선택). 추정 매출 종류 selectbox → **`st.radio` horizontal**. 둘 다 baseweb popover 사용 안 함 |
| 3 | P10/P8: file_datas tuple hashing | `_file_datas_signature(name, len, head 8KB sha1)` 도입. cache wrapper 두 개로 분리: `_load_sales_cached_by_sig` (인자에 `_file_datas` 가 `_` 접두사라 cache hash 제외) + 기존 시그니처 호환 wrapper. 추가로 file_uploader 의 `getvalue()` 가 매 rerun 마다 50MB×N 복사하던 것 → `uploader_sig` 비교 후 변경 시에만 갱신 |
| 4 | S1: ← 처음으로 정리 키 부족 | `_go_to_query_page` 가 `rate_*`, `quick_*`, `quick_picker_open` 모두 정리. file_datas / uploader_sig 보존 |
| 5 | P1: extract_all_contents 호출 자체는 cache hit 비용 작아 유지. 효과적 fix 는 ★3 의 file_datas 해싱 비용 제거 |
| 6 | P5/P7: expander 안 코드 매 rerun 평가 | 결과 페이지 상단 ‘🔍 콘텐츠 조회/추가’ 영역을 expander → **토글 button + session_state** 로 교체. 닫혀 있을 때는 안의 코드(검색·버튼·extract 호출) 자체가 평가 안 됨. 재조회 후 자동으로 닫힘 |
| 7 | S3: rate widget 첫 렌더 캐시 미스 | rate widget 렌더 직전에 `if widget_key not in st.session_state: st.session_state[widget_key] = float(default_rate)` 로 미리 set. 첫 cache 호출도 동일 값으로 hit 가능 |

**미적용 항목 (다음 세션 후보)**:
- B1~B4, R1~R10 의 대부분: 발생 조건이 좁거나 “경고” 수준 (문서화만)
- ★8 이후: P2 (compute_flat_estimates 중복 호출 — cache 화), P4 (stack 비용), P11 (df hash), S4 (extract_all_contents 호출 횟수)

### 3.2. expander chevron 깨짐 마지막 처리 (`52c8fa4`)

**현상**: ‘파일 처리 현황 (8개)’ expander 헤더 왼쪽에 `_arrow_drop_down` ligature 가 한글 폰트로 깨져 라벨 위에 겹쳐 표시.

오전 세션의 `67fec84` 에서 svg/i/[class*="icon"]/`::-webkit-details-marker` 만 hide 했으나, 사용자 환경의 chevron element 가 다른 형태(span 또는 다른 클래스). 셀렉터 다중화:

```css
[data-testid="stExpander"] summary svg,
[data-testid="stExpander"] summary i,
[data-testid="stExpander"] summary [class*="icon"],
[data-testid="stExpander"] summary [class*="Icon"],
[data-testid="stExpander"] summary [class*="material"],
[data-testid="stExpander"] summary [class*="Material"],
[data-testid="stExpander"] summary [data-testid*="icon"],
[data-testid="stExpander"] summary [data-testid*="Icon"],
[data-testid="stExpander"] summary [data-testid*="Chevron"],
[data-testid="stExpander"] summary [data-testid*="chevron"],
[data-testid="stExpander"] summary [aria-label*="rrow"],
[data-testid="stExpander"] summary [aria-label*="hevron"],
details[data-testid="stExpander"] summary::-webkit-details-marker,
details[data-testid="stExpander"] summary::marker {
    display: none !important;
    color: transparent !important;
    font-size: 0 !important;
    width: 0 !important;
    height: 0 !important;
    visibility: hidden !important;
}
```

다층 hide(`display:none + visibility:hidden + 0 size + transparent`) 로 어떤 우선순위 충돌도 견딤. 사용자 추후 보고 없음 → 작동.

### 3.3. 추정 매출 종류 — B-1 기본 + 기타 토글 (`a89311e`, `abf3c4f`)

**1차 (`a89311e`)**:
```
☐ 기타 매출 종류에서 선택 (N개)
[B-1, B-2, B-3J, …] (체크되면)
또는 "추정 매출 종류: **B-1** (기본)" (미체크 시)
```

**2차 (`abf3c4f`)** — 사용자 정정 “체크박스를 추정 매출 종류 ‘아래’로”:
```
추정 매출 종류: **B-1** (기본)
☐ 기타 매출 종류에서 선택 (N개)

→ 체크 시:
추정 매출 종류 (radio horizontal)  ← 위 표시가 radio 로 바뀜
☐ 기타 매출 종류에서 선택 (N개)
```

session_state 키: `show_other_bill{key_suffix}` (불 변수). B-1 이 sales_log 에 없는 환경 fallback 유지.

### 3.4. 콘텐츠 검색 자동완성 (`8763d07` → `6085cec`)

**1차 (`8763d07`)** — 풀 자동완성:
- `_rank_matches(all_contents, kw)`: prefix(score 1000-len) > substring(500-len) > 공백무시(200-len). 같은 그룹은 짧은 제목 우선.
- `_highlight_match(text, kw)`: 매칭 부분 markdown bold (case-insensitive).
- `_render_content_search_section()`: 검색 input + 결과 표시 헬퍼. query 폼 / quick picker 둘 다 호출.
- text_input 의 `on_change` 콜백으로 Enter 시 첫 결과 자동 추가 + 검색어 자동 비움.
- 기본 10개 + “더 보기 (남은 N개)” 버튼으로 30개까지.

**2차 (`6085cec`)** — 사용자 정정 “자동 추가 말고, 추천만”:
- `on_change` 콜백 제거.
- 라벨 “(Enter 로 첫 결과 자동 추가)” 제거.
- caption 의 `Enter 로 첫 결과 자동 추가` 안내 제거. `최대 N개 선택됨` 만 남김.
- 추가는 각 행의 `➕ 추가` 버튼 클릭으로만.

매칭 정렬·하이라이트·“더 보기” 는 그대로 유지.

### 3.5. 메트릭 카드 자동 폰트 축소 (`63dde9d`)

긴 숫자가 카드 폭을 넘어 `...` 으로 잘리던 문제.

```css
[data-testid="stMetric"] {
    container-type: inline-size;
}
[data-testid="stMetricValue"] {
    font-size: clamp(0.85rem, 11cqw, 1.7rem) !important;
    line-height: 1.15 !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: clip !important;
}
[data-testid="stMetricValue"] > div {
    font-size: inherit !important;
    /* ... */
}
```

`cqw` (container query width unit) — 카드 폭의 11% 비율로 폰트 자동 스케일. 모던 브라우저(Chrome 105+, Safari 16+) 지원. 큰 화면에서도 max 1.7rem, 작은 카드도 min 0.85rem 으로 클램프.

### 3.6. 메트릭 라벨 핑크 하이라이트 (`ae3d306` → `cc0eb88` → `a531709`)

**1차 (`ae3d306`)** — `inline-block + padding 3px 10px + border-radius 8px + width auto`. 사용자 “너무 뚱뚱해”.

**2차 (`cc0eb88`)** — 형광펜 스타일:
```css
[data-testid="stMetricLabel"] > div,
[data-testid="stMetricLabel"] p {
    background-color: #FFE5EE !important;
    padding: 0 4px !important;
    border-radius: 4px !important;
    display: inline !important;
    line-height: 1.4 !important;
    box-decoration-break: clone !important;
    -webkit-box-decoration-break: clone !important;
}
```

`box-decoration-break: clone` — 줄바꿈 시 각 줄에 padding/border-radius 동일 적용 (라벨 길어질 때 안전).

**3차 (`a531709`)** — `margin-bottom: 0.6rem` 추가로 라벨과 value 사이 여백.

### 3.7. 차트 급락 마커 ▼ (`ab8db2a`)

`symbol="x"` → `triangle-down`, size 11 → 13, line `width=2` → `width=1, color="white"` (라인 위에서 분리감). 캡션도 `빨간 X` → `빨간 ▼` 동기화.

### 3.8. FLAT 감가 계수 조정 (`0350c15`)

`FLAT_DEPRECIATION = 0.7` 상수는 default 로 유지. `compute_flat_estimates` / `build_excel_export` / `_build_excel_export_cached` 모두 `depreciation: float = FLAT_DEPRECIATION` 인자 추가.

`render_flat_estimates` 의 표 위에 `st.number_input("감가 계수", min=0.0, max=1.0, value=0.7, step=0.05, format="%.2f", key="flat_depreciation")` 노출 (`st.columns([1, 3])` 로 좁게). caption 도 `× {depreciation:.2f}(감가)` 동적.

엑셀 다운로드 시 `_build_excel_export_cached(df, tuple(found_ids), depreciation=float(st.session_state.get("flat_depreciation", FLAT_DEPRECIATION)))`. cache 키에 depreciation 포함되어 값 변경 시 새 엑셀 생성.

### 3.9. 합계 카드 5개 grid + 전체 합계 1번 (`82c3646`, `c3981f4`)

**1차** — `render_yearly_summary` 가 `items: list[(label, value, delta)]` 로 평탄화 → 5개 청크로 chunked 렌더:

```python
per_row = 5
for start in range(0, len(items), per_row):
    chunk = items[start:start + per_row]
    cols = st.columns(per_row)  # 5칸 고정 → 마지막 행 카드 너비도 동일
    for col, (label, value, delta) in zip(cols, chunk):
        with col:
            st.metric(label=label, value=value, delta=delta, delta_color="off")
```

**2차** — items 빌드 순서 변경: 전체 합계가 첫 번째.

### 3.10. 콘텐츠 선택 5개 (`a80e159`)

`>= 3` → `>= 5`, `최대 3개` → `최대 5개`, `min(3, …)` → `min(5, …)` 모두 동기화. 모듈 docstring 의 `1~3개` 는 미동기화 (다음 세션 cleanup 후보).

---

## 4. 현재 상태 — 다음 세션이 알아야 할 사실

### 4.1. 페이지 흐름 (오전 워크로그와 동일, 5-cap 으로 갱신)

```
require_password()
  ↓
_render_title("SVOD 콘텐츠 매출 분석")
  ↓
session_state["step"]
  ├─ "query"  →  render_query_page()  →  _render_query_form()
  │     1. 엑셀 파일 업로드 (uploader_sig 비교, getvalue 절약)
  │     2. 매출 종류 필터 (체크박스 grid, 기본 전체 체크)
  │     3. 추정 매출 옵션 — "추정 매출 종류: **B-1** (기본)" 텍스트만,
  │                       그 아래 ☐ 기타에서 선택 (체크 시 radio 펼침)
  │                       기본 요율 number_input
  │     4. 콘텐츠 선택 — 검색 input + ➕ 결과 버튼 (최대 5개)
  │                     선택된 콘텐츠는 위쪽 영역에 라벨 + [제거]
  │     [조회] 버튼
  │
  └─ "result" →  render_result_page()
        ├─ "← 처음으로" 버튼 (rate_*, quick_*, quick_picker_open 정리)
        ├─ 토글 button "🔍 콘텐츠 조회/추가" (session_state quick_picker_open
        │   ON 시에만 _render_quick_content_picker 평가)
        ├─ ⚙️ 콘텐츠별 요율 설정 (rate_<cid> number_input, 한 줄 최대 5개)
        ├─ 비교 콘텐츠 + 📥 엑셀 다운로드 (감가 계수 반영)
        ├─ 추정치 포함 배너
        ├─ 📈 매출 추이 비교 (급락 마커 ▼ triangle-down)
        ├─ 💰 FLAT 예상 금액
        │     - 감가 계수 number_input (0.0~1.0, default 0.7, key=flat_depreciation)
        │     - 표 (계산 방식 caption 도 동적 감가값 표시)
        ├─ 📋 연간 합계 비교
        ├─ 📋 월별 상세 비교
        └─ 🔍 콘텐츠별 상세 (콘텐츠당 expander)
              내부: render_yearly_summary
              [전체 합계, 2020 합계, 2021 합계, ...] 한 줄 5개 grid
              + 라벨 핑크 하이라이트 (형광펜) + value 자동 폰트 축소
              + 연도×월 피벗
```

### 4.2. session_state 키 인벤토리

| 키 패턴 | 라이프 | 용도 |
|---|---|---|
| `step` | 영구 | "query" / "result" |
| `file_datas` | 영구 (← 처음으로 보존) | list[(name, bytes)] |
| `uploader_sig` | 영구 | (file_id or name, size) tuple — getvalue 재호출 방지 |
| `query` | 조회 후 | dict {content_ids, selected_categories, estimate_bill_type, default_rate} |
| `selected_content_ids{suffix}` | 영구 | query 폼 누적 선택 (← 처음으로 시 보존, query 와 sync) |
| `content_search{suffix}` | 영구 | 검색어 입력값 |
| `cat_<카테고리>{suffix}` | 영구 | 매출 종류 체크박스 상태 |
| `bill_type{suffix}` | 영구 | 추정 매출 종류 radio 선택값 (기타 토글 시) |
| `show_other_bill{suffix}` | 영구 | 기타 종류 체크박스 |
| `default_rate{suffix}` | 영구 | 기본 요율 number_input |
| `show_more_search{suffix}` | 영구 | 검색 결과 더 보기 토글 |
| `quick_selected_ids` | result 진입~ | quick picker 누적 선택 |
| `quick_content_search` | result | quick picker 검색어 |
| `quick_picker_open` | result | 토글 button 상태 |
| `rate_<cid>` | result | 콘텐츠별 요율 number_input |
| `flat_depreciation` | 영구 | FLAT 감가 계수 (default 0.7) |
| `authed` | 영구 | require_password 통과 표시 |

`_go_to_query_page` 가 정리: `rate_*`, `quick_*`, `quick_picker_open`. **유지**: file_datas, uploader_sig, query, selected_content_ids*, cat_*, bill_type*, show_other_bill*, default_rate*, flat_depreciation, authed.

### 4.3. CSS 인벤토리 (다음 세션 수정 시 의식)

- **글로벌 폰트**: `.stApp / .stApp * + button/input/select/textarea/label` 만 강제. `[class*="st-"]` 절대 사용 X (portal 까지 휩쓸어서 baseweb 깨짐).
- **fileUploader 안 button 모두 `display:none`**: 메인 업로드도 안 보임. dropzone 클릭/드래그로 업로드.
- **expander summary 의 chevron**: 다중 셀렉터 + 다층 hide. ligature 텍스트 노출 방지.
- **도움말(?) 아이콘**: 모두 `display:none`. `help=` 인자 추가해도 화면 안 나옴.
- **listbox max-height: 280px** + `[role="option"]` 색·배경 명시. 매출 종류 multiselect 는 사라졌지만 selectbox 가 어디 다시 등장할 경우 대비.
- **메트릭 카드**: `container-type: inline-size` + value 폰트 `clamp(0.85rem, 11cqw, 1.7rem)`. 라벨은 `inline + 핑크 하이라이트 + box-decoration-break: clone`. 라벨-value 간격 `margin-bottom: 0.6rem`.

### 4.4. 캐시 인벤토리

- `_read_*_sheet`, `_get_sheet_names`, `_estimated_factor_monthly`, `_content_watch_minutes_by_month`, `_viewing_log_total_by_month`, `_sales_log_by_type_month`, `_sales_log_type_column`, `extract_sales_log_types`, `extract_all_contents`, `extract_sales_categories`, `_load_sales_cached_by_sig`, `_build_excel_export_cached` 모두 `@st.cache_data(show_spinner=False)`.
- **bytes hash 비용 회피**: `_load_sales_cached` 가 `_file_datas_signature` (name+len+head 8KB sha1) 만 cache key 로 사용. file_datas 자체는 `_` 접두사로 hash 제외.
- **getvalue 재호출 회피**: `uploader_sig` 비교 후 변경 시에만 `[(f.name, f.getvalue()) for f in files]` 새 list 생성.

---

## 5. 막다른 골목과 결정사항

### 5.1. 자동완성 Enter 자동 추가는 거부됨 (5.→6. 정정)

“자동완성” = 키워드 매칭 자동 추천만. Enter 로 첫 결과 자동 추가는 사용자 의도와 다름. 다음 세션에서 “Enter 로 자동 추가” 류 제안 다시 X.

### 5.2. multiselect / selectbox / dropdown popover 다시 도입 X

코드 리뷰 ★2 에서 매출 종류 multiselect 도 체크박스 grid 로, 추정 매출 종류 selectbox 도 radio 로 교체. 사용자 환경에서 popover 깨짐이 일관되게 발생하므로 새 위젯 추가 시 popover 우회 패턴 사용:
- 적은 옵션(<10): radio horizontal
- 중간 옵션(10~30): 체크박스 grid
- 많은 옵션(30+): 검색 input + 결과 버튼 (현재 콘텐츠 선택 패턴)

### 5.3. 라벨 핑크 하이라이트는 형광펜 스타일

`inline + padding 0 4px + border-radius 4px + box-decoration-break: clone`. 첫 시도(inline-block + padding 3 10) 는 “너무 뚱뚱” 으로 거부됨. 다음 세션에서 다른 영역(예: section heading) 핑크 하이라이트 시 같은 패턴 사용.

### 5.4. 메트릭 카드 폰트 = container query

`container-type: inline-size` + `clamp(min, Ncqw, max)` 패턴. vw 단위 X (viewport 기준이라 카드 1개 vs 6개 grid 에서 동일 비례 안 됨).

### 5.5. file_datas 시그니처 캐시는 head 8KB sha1

전체 50MB 해싱 회피. 첫 8KB 가 다르면 다른 파일로 간주 — 정상 사용 케이스에서 충분. 단 “같은 헤더 + 다른 본문” 인 의도적 두 파일은 같은 시그니처(현실엔 거의 없음).

---

## 6. 다음 세션 후보

**즉시 cleanup 가능**:
- [ ] 모듈 docstring 의 `1~3개` 를 `1~5개` 로 동기화 (`a80e159` 에서 누락)
- [ ] `flat_depreciation` 값을 `_go_to_query_page` 에서 정리할지 결정 (현재 보존)
- [ ] `selected_content_ids{suffix}` 도 ← 처음으로 시 정리할지 검토 (현재 보존, 의도상 “돌아갔을 때 이전 선택 유지”)

**남아있는 코드 리뷰 항목** (★8 이후):
- [ ] B1~B4: 사소한 가독성·안전망. 거의 발생 X 라 우선순위 낮음
- [ ] R1~R10: 대부분 “경고 발생 가능성” 수준. UI 영향 없음
- [ ] P2: `compute_flat_estimates` 가 화면 한 번 + 엑셀 시트 한 번 호출. cache 적용 가치 있음
- [ ] P4: `pivot.iloc[:, :12].stack()` future_stack 권장 (pandas 2.3 FutureWarning)
- [ ] P11: download_button 의 cache hit 검증 (현재는 OK 추정)

**남아있는 어제 12절 후보**:
- [ ] 2020~2024 파일 실제 테스트 — `_to_month_timestamp` 다양한 월 표기
- [ ] bill_name ↔ type 매핑 테이블
- [ ] 추정 요율 자동 추천 (다른 매출종류 / 유사 콘텐츠 평균)
- [ ] viewing_log 시청분수 트렌드 별도 뷰
- [ ] 요율 일괄 적용 / 프리셋 저장·복원
- [ ] 차트 “급락 임계값(-30%)” 사이드바/감가 입력 옆에 노출 (현재 사이드바 비움 → 본문에 옵션 영역 신설 필요)
- [ ] calamine Streamlit Cloud 가용성 재확인 (어제부터 후보)
- [ ] viewing_log 콘텐츠별 인덱싱 통합

**이번 세션에서 새로 떠오른 후보**:
- [ ] **“최근 검색한 콘텐츠 N개” 빠른 클릭** — 검색 input 비어있을 때 노출
- [ ] **콘텐츠 선택 5개로 늘렸으니 차트 가독성 검증** — 현재 팔레트 3색이라 4·5번째 콘텐츠는 색 반복. 팔레트 5색으로 확장 필요
- [ ] **합계 카드 5칸 grid 의 마지막 행이 1~2개일 때** — 빈 칸이 보임. CSS 또는 동적 columns 로 가운데 정렬 또는 좌측 채움 옵션
- [ ] **감가 계수 변경 시 엑셀 cache 무효화** — 이미 cache key 에 포함되어 있으니 OK 이지만 첫 변경 시 재빌드 비용 시각화(`spinner`?)
- [ ] **콘텐츠별 상세 expander 헤더의 ▼ 아이콘 부재** — 펼침 상태 시각화가 약함. ::before 로 ▸/▾ 텍스트 마커 추가 검토
- [ ] **expander 의 collapsed/expanded 시각 보강** — chevron 숨겼으니 hover 시 배경 핑크 정도라도

---

## 7. 사용자 스타일 추가 관찰 (오전 7절 보강)

- **연속 미세 정정 모드**: 한 영역에 대해 2~3번 작은 수정이 들어옴 (예: 핑크 하이라이트 `padding 3 10` → `padding 0 4` → `margin-bottom 0.6rem`). 한 번에 “완성도 높은 안” 을 추측하기보다 **빠른 1차 시도 + 사용자 정정 사이클**이 더 효율적.
- **추천 요청 패턴**: “기호 추천 좀 해줘” 처럼 옵션 제시 요청. 짧은 표 + 1·2순위 추천 + 사용자 “1순위 적용” 으로 한 라운드. 옵션 5개 이내가 적당.
- **이해 한 후 정정**: “자동 추가 말고” 처럼 우리가 제안한 기능 중 일부만 거부. 거부 부분을 정확히 식별하고 해당 코드만 빼야 함 (자동완성 정렬·하이라이트는 유지).
- **숫자/순서 변경 요청**: 단순 상수 변경처럼 보여도 여러 위치 동기화 필요 (5-cap = full 판정 + hint + caption + 컬럼 grid + 페이지 안내). grep 으로 모든 occurrences 확인.

---

## 8. 디버깅·재발 방지 메모 (오전 8절 보강)

### 8.1. ★ Streamlit container query
`container-type: inline-size` 를 부모에 설정하면 자식의 `cqw` (container query width) 단위가 그 부모 폭 기준으로 동작. `vw` (viewport) 와 다름. 카드/columns layout 에서 폰트 자동 스케일 시 필수.

### 8.2. ★ box-decoration-break: clone
inline element 가 줄바꿈될 때 각 라인에 padding/border-radius/border 를 동일 적용. 형광펜 스타일 하이라이트가 한 줄짜리든 여러 줄이든 깨끗하게 보임. webkit prefix 같이 쓰기.

### 8.3. ★ Streamlit cache_data 의 `_` 접두사
`_load_sales_cached_by_sig(signature, ..., _file_datas)` 처럼 매개변수 이름을 `_` 로 시작하면 cache key hashing 에서 제외. 큰 객체(예: bytes list) 의 sha256 비용 회피하면서도 함수 호출 시 그 객체 사용 가능. 첫 miss 시점에만 _file_datas 가 실제 사용되고, 이후 cache hit 은 이전 결과 반환.

### 8.4. ★ st.text_input 의 on_change
키 바뀔 때(blur 또는 Enter) 콜백 트리거. 자동 추가 같은 부작용은 사용자가 명시 거부할 수 있음. 신중하게.

### 8.5. ★ Plotly marker symbol 후보
`triangle-down`, `arrow-down`, `arrow-bar-down`, `diamond-x`, `circle-x`, `star-triangle-down` 등 “하강/경고” 의미. 사용자에게 옵션 표 + 추천 1·2순위로 제시.

### 8.6. ★ session_state 정리는 startswith 패턴
`for k in list(st.session_state.keys()): if isinstance(k, str) and k.startswith("rate_"): del st.session_state[k]` — `list()` 로 snapshot 떠야 iteration 중 mutate 가능.

### 8.7. ★ st.columns 5칸 고정 grid
`per_row = 5; for chunk in chunks: cols = st.columns(per_row); for col, item in zip(cols, chunk): ...`. 마지막 chunk 가 적어도 5칸 grid 가 유지되어 카드 너비 일관됨.

---

## 9. 다음 세션 시작 시 권장 첫 단계

1. **이 문서 + 오전 워크로그(`2026-04-29-feature-then-font-and-multiselect-rework.md`) + 어제(`2026-04-28-...`) + 그저께(`2026-04-27-...`) + MVP(`2026-04-23-...`) 모두 훑기**.
2. `cat ~/.claude/projects/-Users-linazzang/memory/MEMORY.md` 인덱스 확인.
3. `git log --oneline -30` (이번 워크로그 자체가 마지막일 것).
4. **gh CLI** `ls -la /tmp/gh-bin` (단일 바이너리). 없으면 오전 9.1 절차로.
5. **로컬 환경**: `cd ~/Projects/contentsefficiency && .venv/bin/streamlit run app.py`.
6. **배포 앱** https://watcha-content-efficiency.streamlit.app HTTP 303 확인.
7. 6절 후보 검토. **5.1~5.4 의 결정사항(자동 추가 X, popover 사용 X, 형광펜 패턴, container query)** 을 기억하고 새 제안 시 충돌 검토.

---

## 10. 부록 — 이번 세션 사용자 메시지 흐름 (요약)

- “Streamlit 앱 전체 리뷰 — 4가지 카테고리, 추측 말고 코드 근거” → 17개 항목 정리
- “1부터 7번 다 진행” → `d83c255`
- “파일 처리 현황 부분 글자 겹쳐” → `52c8fa4`
- “추정 매출 옵션 — B-1 기본 + 기타 토글” → `a89311e`
- “기타 체크박스를 추정 매출 종류 아래로” → `abf3c4f`
- “콘텐츠 검색 자동완성” → `8763d07`
- “자동 추가 말고 자동 추천만” → `6085cec`
- “메트릭 value 폰트 자동 축소” → `63dde9d`
- “라벨 연한 핑크 하이라이트” → `ae3d306`
- “하이라이트 너무 뚱뚱해 글자에 맞춰서” → `cc0eb88`
- “합계 아래 한줄 띄워줘” → `a531709`
- “급락 X 다른 기호 추천” → 옵션 제시
- “1순위 적용” (▼) → `ab8db2a`
- “FLAT 감가 0.7 기본 + 조정 가능” → `0350c15`
- “합계 카드 6개부터 줄 구분, 1줄 5개” → `82c3646`
- “전체 합계 1번으로” → `c3981f4`
- “콘텐츠 조회 최대 5개” → `a80e159`
- “워크로그 작성하자.” → 본 문서

각 요청마다 **추가 컨텍스트 질문 없이 즉시 구현·푸시**가 표준. 폰트 깨짐 디버깅이 끝나고 UX 폴리시 단계라 정정 사이클이 길지 않음(보통 1~2회).
