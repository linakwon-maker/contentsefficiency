# 2026-04-29 · 기능 추가 (엑셀 다운로드·페이지 분리) → 디자인 → 폰트 깨짐 사투 → multiselect 자체 교체

> **작성 목적**: 다음 세션에서 이 프로젝트를 이어 작업할 때 빠르게 맥락을 복구. 오늘은 **25 커밋, app.py 1452 → 1870줄(+418)** 의 큰 변동. 흐름이 “기능 추가 → 디자인 → 폰트/UI 깨짐 디버깅 사투 → 결정적 우회” 라 시간순 + 교훈 중심으로 정리. 코드는 git 으로 볼 수 있으니 **숨은 결정 / 막다른 골목 / 재발 방지**에 집중.
>
> 이전 워크로그: `2026-04-23-mvp-launch.md`, `2026-04-27-rate-editor-perf-ux-polish.md`, `2026-04-28-branding-watcha-pedia-tone-and-perf.md`. 이 문서는 그 후속.

---

## 0. TL;DR — 오늘 25 커밋 한 줄 요약 (시간순)

| # | 해시 | 메시지 | 핵심 |
|---|------|--------|------|
| 1 | `2e4ea73` | feat: 추정치 시각 구분 + FLAT 추정 포함 표시 + 엑셀 다운로드 | 차트 점선·표 음영·FLAT 추정월 컬럼·xlsx 다운로드 4종 시트 |
| 2 | `cf7cd12` | revert+perf: 추정치 시각 구분 롤백 + 조회 속도 개선 | **사용자가 추정치 시각 구분 명시 거부** → 1번에서 추가한 차트 점선·표 음영·FLAT 추정월 컬럼 모두 원복. 동시에 `_load_sales_cached` / `_build_excel_export_cached` 캐시 wrapper, `_to_number` 벡터화 |
| 3 | `d92e325` | feat(excel): 콘텐츠별 상세 시트에 연간 합계·평균·총합 행/열 추가 | 화면 표와 동일하게 |
| 4 | `5b3c7e3` | feat(excel): 다운로드 엑셀의 모든 숫자 셀에 천단위 구분기호 적용 | openpyxl `cell.number_format = "#,##0"`. 인덱스(연도) 는 의도적으로 제외 |
| 5 | `81b39e0` | style: 귀여운 핑크 파스텔 톤으로 디자인 리프레시 | 라디얼 핑크 그라디언트·메트릭 핑크박스·차트 팔레트 핑크/민트/버터 |
| 6 | `52cf8cf` | style: 배경 톤 원복 (흰/그레이) — 핑크 액센트는 유지 | **사용자가 "배경 너무 핑크" 지적** → 배경/메트릭/expander/차트 모두 원복. 핑크는 액센트(버튼·도트·로고 그림자)만 |
| 7 | `dd6a242` | style: 화면 타이틀에서 'WATCHA' 제거 (로고와 중복 회피) | `_render_title("SVOD 콘텐츠 매출 분석")`. `page_title` 은 그대로 |
| 8 | `684784a` | style: 글로벌 폰트를 Apple SD Gothic Neo 로 (fallback 포함) | CSS `font-family !important` + Plotly font family. **이후 모든 폰트 깨짐의 출발점** |
| 9 | `a9a5763` | style(uploader): 버튼 텍스트가 버튼 폭을 넘쳐 보이는 문제 수정 | nowrap·padding·폰트 0.85rem (1차 시도, 효과 없음) |
| 10 | `ebd56c0` | fix(uploader): 좁은 사이드바에서 dropzone 텍스트 겹침 해결 | 사이드바 min-width 300 + dropzone column stack (2차, 오히려 악화) |
| 11 | `89f342d` | fix(uploader): dropzone 자식 텍스트 이중 렌더 원인 제거 | 10번에서 추가한 column 강제 모두 제거 (3차, 실제 원인 아님) |
| 12 | `acde9cd` | fix(uploader): 버튼 텍스트 이중 렌더 — 원본 텍스트 가리고 라벨 직접 주입 | button 자식 visibility:hidden + ::after `파일 선택` (4차, 'upload' 두 번은 사라짐) |
| 13 | `c39b368` | fix(font): Material Icons 아이콘이 한글 폰트로 깨지는 문제 수정 | `?` 도움말 아이콘 → `뀀` 처럼 깨짐. Material Symbols 셀렉터 우선 (효과 없음) |
| 14 | `2215b62` | fix(font): 도움말(?) 아이콘 자체를 숨김 | display:none 다중 셀렉터. **이 시점부터 `help=` 인자 사실상 무력화** |
| 15 | `1657d76` | feat(ux): 화면 구성을 단계별 페이지로 분리 | `step` session_state 분기. `render_query_page` / `render_result_page` + `_render_query_form()` 함수 추출. 사이드바 비움. 결과 페이지 상단 expander 에 빠른 콘텐츠 변경 |
| 16 | `1da3d10` | fix(font): 이모지/NaN 텍스트 깨짐 정리 | 폰트 스택에 emoji 폰트 명시, `🏁 전체 합계` → `전체 합계`, `월평균 nan` → `월평균 -` |
| 17 | `322ff14` | fix(font): fileUploader 영역 폰트를 Streamlit 기본으로 revert | 파일 항목 옆 `웹`/`일선` 깨짐 — Material Icons ligature 가 한글 폰트로 fallback. revert 시도(효과 미미) |
| 18 | `d91af1b` | fix(font): fileUploader 버튼 일체 숨김 + dropdown 옵션 글자 색·폰트 강제 | **결정적**: `[data-testid="stFileUploader"] button { display: none }`. 깨진 글자 사라짐. dropzone 클릭/드래그는 그대로 동작 |
| 19 | `4932c9c` | fix(font): dropdown 옵션 셀렉터 강화 — body 직속 portal 포괄 | multiselect 옵션 안 보임 — 1차 시도 |
| 20 | `cfebcea` | fix(font): dropdown 옵션 — body 직속 portal 전체에 색·폰트 강제 | 2차 시도 |
| 21 | `8b5c017` | fix(font): dropdown 옵션 — role=listbox/option 에 색·폰트·opacity·visibility 강제 | 3차 시도 |
| 22 | `a976b41` | fix(font): body 모든 글자 검은색 강제 (흰 글자 버튼·태그 예외) | 4차, nuclear `body * { color !important }` |
| 23 | `67fec84` | fix: expander chevron 'arrow_right' 텍스트 노출 + 차트 'undefined' 표시 제거 | expander summary 의 svg/i 숨김. Plotly title `{"text":"", "x":0}` |
| 24 | `3938522` | fix(font): 글로벌 폰트 적용 범위를 stApp 안으로 한정 + dropdown 옵션 룰 단순화 | `[class*="st-"]` 제거 → `.stApp .stApp *` 만 강제. body * color 제거. listbox max-height 280 |
| 25 | `cdc53d3` | fix(ux): 콘텐츠 선택을 검색 input + 결과 버튼 방식으로 교체 (multiselect 제거) | **결정적 우회**. multiselect dropdown popover 의 옵션 글자가 환경별 끝까지 안 보임 → text_input 검색 + 매칭 결과 30개 버튼 리스트로 교체. 선택은 session_state 누적 (최대 3개) |

세션 결과: app.py **1452 → 1870줄 (+418)**. 새 파일 없음. 메모리도 그대로(`MEMORY.md` 외 갱신 없음).

---

## 1. 시작 상태 (= 어제 워크로그 끝)

- 마지막 커밋: `7a995af` (어제 워크로그 자체).
- 사용자 표준 진입: “저번 작업 이어서 할게” → 메모리 + `docs/worklogs/2026-04-28-...md` 의 12절(다음 후보) / 13절(권장 첫 단계) 보고 후보 제시.
- gh CLI 는 `/tmp/gh-bin` 에 살아있었고, repo-local git config 도 OK, 배포 앱 HTTP 303.

---

## 2. 사용자 요구 (시간 순)

**기능 추가 단계** (1~4):
1. “기능 추가의 1·2·3번 하자” = 어제 12절 후보의 (a) 추정치 시각 구분, (b) FLAT 예상에 추정치 포함 표시, (c) 결과 엑셀 다운로드.
2. **“추정치 구분 및 표시는 안해도 될거 같아 그것만 되돌려줘”** — 1번에서 추가한 추정치 관련 시각 변경(차트 점선·표 음영·FLAT 추정월 컬럼) 모두 거부. 엑셀 다운로드는 유지.
3. “조회 누르고 나서 엑셀 파일 분석이 너무 오래 걸린다 더 빠르게 못해?” → cache wrapper.
4. “콘텐츠별 상세 탭에 연간 합계와 연간 평균 데이터도 포함되게 해줘” / “엑셀 파일에서도 1000단위 구분기호 사용해서 보여줘”.

**디자인 단계** (5~8):
5. “디자인을 좀 더 귀엽게 손보자” → 핑크 파스텔.
6. **“배경색 너무 핑크야;; 원래 색으로 돌려줘”** — 5번 거의 전부 원복.
7. “맨 위 제목에 이미 로고가 있어서 WATCHA는 빼도 될거 같아 지워줘”.
8. “지금 적용된 폰트는 뭐야?” → Streamlit 기본 안내. “Apple SD 산돌고 Neo 로 바꿀 수 있어?” → 적용. **이게 이후 모든 깨짐의 시작**.

**폰트 깨짐 사투** (9~14, 17~24):
- “폰트 튀어나온 거 보여? upload 버튼 크기에 맞춰서 조정해줘” (스크린샷에 `uploadpload` 두 번 어긋나 겹침)
- “아직도 넘치잖아;;다시” / “아직도 안 맞잖아 생각 좀 잘해봐” / **“지금 같은 문제로 3번째 물어보고 있어 이번엔 제대로 수정해줘”**
- “upload 글자는 해결이 됐는데 옆에 이상한 글자 겹쳐진 거? … 없애” (도움말 아이콘 자리에 `뀀`)
- “여전히 업로드한 엑셀 파일마다 이상한 글자가 붙어있어 그냥 없애줘 저 글자” (파일 항목 옆 `웹`/`일선`)
- “와 글씨 깨지는 거 미쳤나봐 없애줘” (메트릭 라벨 등)
- **결과 페이지 dropdown 옵션 안 보임**: “콘텐츠 검색 했을 때 글자가 안 안보여 수정해줘” → 5회 반복 → “미친 아직도 안보이잖아 제발 어떻게든 고쳐봐”

**구조 변경** (15):
- “화면 구성 순서를 바꿔보자 — 비밀번호 → 파일 업로드/조회 → 결과 / 결과 페이지 최상단에 콘텐츠 조회 기능”

**워크로그**:
- “워크로그 작성하자.”

---

## 3. 변경 요점 — 그룹별 정리

### 3.1. 추정치 시각 구분 — 추가 후 즉시 롤백 (사용자 거부)

**`2e4ea73` 에서 시도, `cf7cd12` 에서 원복.**

- 차트 `render_comparison_chart`: 실측 실선 + 추정 dash trace 분리. 전환 지점 한 점 공유로 끊김 없는 전환. open-circle 마커.
- 표 `render_pivot` / `render_monthly_comparison`: Styler `apply` + mask DataFrame 으로 추정 셀에 핑크 음영 (`#FFF1F4`). pandas 2.3 → `applymap` 대신 `DataFrame.map` 사용.
- `compute_flat_estimates`: window 내 추정월 카운트 → "추정치 포함" 컬럼.
- `render_flat_estimates`: row 단위 apply 로 해당 셀 음영.

**롤백 사유 (사용자 직접)**: “추정치 구분 및 표시는 안해도 될거 같아 그것만 되돌려줘”. **다음 세션에서 이 기능을 다시 제안하지 말 것.** 사용자가 한 번 명시 거부함. 단, 같은 회차에 추가한 **엑셀 다운로드(`build_excel_export`)·`_to_number` 벡터화**는 살아있음.

### 3.2. 엑셀 다운로드 (`build_excel_export`)

`_build_excel_export_cached` (cache_data) wrapper 로 매 rerun 의 재빌드 비용 제거. 4종 시트: 월별 상세 / 연간 합계 / FLAT 예상 / 콘텐츠별 피벗(콘텐츠 1개당 1시트, 시트명 31자 + 엑셀이 거부하는 `[]:*?/\\` 치환 + 중복 회피).

- **콘텐츠별 시트 = 화면과 동일**: 12개월 + 연간 합계·연간 평균 + 마지막 "총합" 행 (`d92e325`).
- **천단위 구분기호** (`5b3c7e3`): `_apply_thousands_format(ws, has_index)` 헬퍼 — 데이터 영역의 `int/float` 셀에만 `cell.number_format = "#,##0"`. 인덱스(연도) 는 `1,234` 처럼 표시되지 않게 의도적으로 제외 (min_col=2 에서 시작). FLAT 시트는 index=False 라 모든 컬럼 적용.
- 다운로드 버튼 위치: 결과 페이지의 “비교 콘텐츠” 라벨 옆 컬럼.

### 3.3. 조회 속도 (`_load_sales_cached`)

`load_sales_from_uploads(file_datas, content_ids, …)` 자체엔 cache 가 없어 매 rerun 재실행이 병목. wrapper 추가:

```python
@st.cache_data(show_spinner=False)
def _load_sales_cached(file_datas_tuple, content_ids_tuple, selected_categories_tuple,
                      estimate_missing, estimate_bill_type, estimate_rates_tuple, default_rate):
    return load_sales_from_uploads(...)
```

`main()` 에서 list/dict 를 모두 hashable tuple 로 정규화해 호출. rate 만 변경되어도 시트 파싱은 기존 내부 캐시(`_read_*_sheet`, `_estimated_factor_monthly`) 가 흡수, wrapper 가 매칭·melt·concat 까지 캐시.

`_to_number` 도 list-comp → `pandas.to_numeric` 벡터화:
```python
rev_str = melted["revenue"].astype("string").str.replace(r"[^0-9.\-]", "", regex=True)
rev_str = rev_str.where(rev_str.str.len() > 0).where(~rev_str.isin({"-", "."}))
melted["revenue"] = pd.to_numeric(rev_str, errors="coerce")
```

### 3.4. 디자인 — 핑크 파스텔 시도 후 부분 원복

`81b39e0` 에서 라디얼 핑크/버터 그라디언트·핑크 메트릭 카드·핑크 보더·차트 팔레트 핑크/민트/버터 (`#FF3D7F / #7AC7E0 / #FFD580`) 적용. 사용자 “배경색 너무 핑크야;;” → `52cf8cf` 에서 페이지/사이드바/메트릭/expander/차트 paper·plot·grid 모두 흰/그레이 라이트로 원복.

**현재 살아있는 핑크**:
- 메인 핑크 색 `_WATCHA_PINK = #FF3D7F` (이전 `#FF0558` 보다 약간 부드러움)
- 버튼 핑크 그라데이션 (`#FF3D7F → #FF6BA0`) + 핑크 그림자
- h2 좌측 핑크 도트 마커 (`::before` content + box-shadow glow)
- 입력 위젯 focus 보더, 호버 효과
- 차트 라인 메인, 로고 그림자 강도, multiselect 태그 배경

**다음 세션 주의**: “귀엽게” 류 요청 다시 오면 **배경 톤은 건드리지 말 것**. 액센트 / 보더 / 그림자 / 마커 정도만 손댄다.

### 3.5. 페이지 분리 (`1657d76`)

`main()` 이 `st.session_state["step"]` 기반 분기:
- 미설정 또는 `"query"` → `render_query_page()`
- `"result"` → `render_result_page()`

사이드바는 비웠음. 위젯은 모두 메인으로:
- `_render_query_form(*, key_suffix="")` 가 1) 파일 업로드 2) 매출 종류 multiselect 3) 추정 옵션 selectbox + number_input 4) 콘텐츠 선택 5) 조회 버튼을 순서대로 렌더. `key_suffix` 로 결과 페이지의 빠른 변경 폼과 위젯 키 충돌 회피.
- 결과 페이지 상단: `← 처음으로` 버튼 + 펼침 expander `🔍 콘텐츠 조회 / 추가` (안에 `_render_quick_content_picker()`).
- `_go_to_query_page()`: 뒤로 갈 때 `rate_*` widget state 일괄 초기화.

콘텐츠가 바뀌어도 같은 처리: `quick_content_picker` 결과 적용 시 `rate_*` 키 정리 후 rerun.

### 3.6. 폰트 — Apple SD Gothic Neo 적용과 그 부작용 6연쇄

`684784a` 에서 글로벌 CSS:
```css
html, body, .stApp, [class*="st-"], button, input, select, textarea, label {
    font-family: "Apple SD Gothic Neo", -apple-system, ..., sans-serif !important;
}
```

이후 사용자 환경에서 줄줄이 깨짐 발생:

**(A) fileUploader 의 `upload` 두 번 겹침** — 4번 시도 끝에 `acde9cd` 의 nuclear (button 자식 visibility:hidden + ::after `파일 선택`) 으로 일시 해결. 그러나 **업로드 후엔 파일 항목 옆 X 버튼에 `웹`/`일선` 깨진 글자**가 별도로 표시.

**(B) Material Icons ligature 깨짐** — Streamlit 의 도움말(?) 아이콘, fileUploader 의 X 아이콘, expander chevron(▶) 등은 모두 `<i class="material-...">help_outline</i>` 같은 ligature 키를 Material Icons / Symbols 폰트로 렌더하는 구조. 우리 글로벌 `font-family !important` 가 그 영역까지 덮어 ligature 키가 한글 폰트로 fallback → `뀀`/`웹`/`일선`/`_arrow_right` 같은 글자가 텍스트로 그대로 그려짐.

**최종 처리**:
- 도움말 아이콘 (`stTooltipHoverTarget` / `stTooltipIcon` / `label svg[viewBox="0 0 16 16"]`): `display: none` (`2215b62`).
- fileUploader 안 모든 button: `[data-testid="stFileUploader"] button { display: none !important }` (`d91af1b`). dropzone 영역 자체는 클릭/드래그로 동작.
- expander summary 의 chevron (svg / i / `[class*="icon"]` / `::-webkit-details-marker`): `display: none` (`67fec84`). summary 클릭만으로 토글 가능.
- 차트 `undefined` 텍스트: Plotly `title=None` 이 문자열로 변환되는 케이스 → `title={"text": "", "x": 0}` 으로 명시 (`67fec84`).
- 이모지 fallback: 폰트 스택에 `"Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji"` 추가 (`1da3d10`).
- 메트릭 NaN 표시: `f"월평균 {avg:,.0f}"` 가 NaN 이면 `"월평균 -"` (`1da3d10`).

### 3.7. dropdown 옵션 안 보임 사투 — 5번 실패 후 multiselect 자체 교체

**현상**: 결과 페이지의 “콘텐츠 조회 / 추가” 또는 조회 폼의 콘텐츠 multiselect 클릭 시 dropdown 박스만 떠있고 옵션 글자가 전혀 안 보임. 핑크 highlighted 줄과 빈 흰 영역만 표시.

**시도 (모두 효과 없음)**:
- `4932c9c`: `[data-baseweb="popover"] *`, `ul[role="listbox"] *`, `li[role="option"] *` 등 셀렉터 다중.
- `cfebcea`: `body > div:not([data-testid="stApp"]):not([data-testid="stHeader"]) *` 로 portal 직속 자손 모두에 색·폰트 강제.
- `8b5c017`: `[role="listbox"]`, `[role="option"]` + 자손에 color·opacity·visibility·font-size 까지 강제.
- `a976b41`: nuclear `body * { color: #1A1A1A !important }` + 흰 글자 필요 부분(primary 버튼·`data-baseweb="tag"`) 만 예외. 그래도 옵션 안 보임.
- `3938522`: 글로벌 `[class*="st-"]` 폰트 강제가 portal 의 emotion 클래스까지 덮어 layout 깨졌을 가설 → `.stApp / .stApp *` 로 한정 + body * color 제거 + listbox max-height 280. 여전히 안 보임.

**결정적 우회 (`cdc53d3`)**: multiselect 컴포넌트 자체를 사용 안 함.

```python
search = st.text_input("콘텐츠 검색", key=f"content_search{key_suffix}", ...)
if search.strip():
    matches = [c for c in all_contents
               if kw in (c.get("title") or "").lower() or kw in str(c.get("id", ""))][:30]
    for c in matches:
        if cid in already: continue
        if st.button(f"➕ {label}", disabled=full, ...):
            st.session_state[state_key] = current_ids + [cid]
            st.rerun()
```

선택된 콘텐츠는 별도 영역에 `📺 라벨 + [제거]` 행. `st.session_state[state_key]` 에 누적, 최대 3개 도달 시 추가 버튼 disabled. 조회 폼(`_render_query_form`) 과 결과 페이지 빠른 변경(`_render_quick_content_picker`) 둘 다 동일 패턴.

**이 결정의 의미**:
- multiselect 의 baseweb dropdown popover 의 옵션 글자 깨짐은 환경별로 일관되게 안 잡힘 (사용자 환경 = macOS Chrome 추정).
- popover 자체를 사용하지 않아 환경 의존성 제거.
- selectbox(추정 매출 종류 B-1) 와 매출 종류 multiselect(`#REF! / B-1 / B-2 / ...` 핑크 태그) 는 **그대로 유지**. 이 둘은 옵션이 짧은 영문/숫자 + 선택된 태그가 별도 표시되어 사용자가 깨짐 보고 안 함. **건드리지 말 것**.

---

## 4. 현재 상태 — 다음 세션 시작 시 알아야 할 사실

### 4.1. 페이지 흐름

```
require_password()  → 비밀번호 통과 (.streamlit/secrets.toml 또는 Cloud Secrets)
   ↓
_render_title("SVOD 콘텐츠 매출 분석")  ← page_title 만 'WATCHA SVOD ...' 그대로
   ↓
session_state["step"]
   ├─ "query" (기본)  →  render_query_page()  →  _render_query_form()
   │                                            (file uploader / 매출 종류 multiselect /
   │                                             추정 옵션 selectbox+number_input /
   │                                             검색-버튼 콘텐츠 선택 / 조회)
   │                       ↓ 조회 클릭
   │                     session_state["query"] = {...}
   │                     session_state["step"] = "result"
   │                     st.rerun()
   └─ "result"        →  render_result_page()
                          ├─ ← 처음으로 (step=query 로 + rate_* 키 초기화)
                          ├─ expander '🔍 콘텐츠 조회 / 추가' → _render_quick_content_picker()
                          │   (검색-버튼 방식. 재조회 누르면 query.content_ids 만 갱신)
                          ├─ ⚙️ 콘텐츠별 요율 설정 (rate_<cid> number_input)
                          ├─ 비교 콘텐츠 라벨 + 📥 엑셀 다운로드
                          ├─ 추정치 포함 배너
                          ├─ 📈 매출 추이 (단일 trace 라인, 추정치 시각 구분 없음)
                          ├─ 💰 FLAT 예상
                          ├─ 📋 연간 합계 비교
                          ├─ 📋 월별 상세 비교
                          └─ 🔍 콘텐츠별 상세 (콘텐츠당 expander, 안에 메트릭 + 피벗)
```

### 4.2. CSS 핵심 결정 (수정 시 반드시 의식)

- **글로벌 폰트는 `.stApp` 안만**: `html, body, .stApp, .stApp *, button, input, select, textarea, label` 에 `font-family !important`. portal popover (multiselect/selectbox dropdown) 는 baseweb 기본 폰트 사용.
- **fileUploader 안 button 은 모두 `display: none`**: 메인 업로드도 안 보임. dropzone 영역 클릭/드래그로만 업로드. 사용자가 이걸 알고 있어야 함.
- **expander chevron 도 숨김**: summary 클릭으로만 토글.
- **도움말(?) 아이콘 모두 숨김**: `help=` 인자가 살아 있어도 화면엔 안 나옴. 새 widget 에 `help=` 추가하지 말 것 (효과 없음).
- **listbox max-height 280px**: 다른 dropdown(매출 종류 multiselect 의 옵션 / 추정 매출 종류 selectbox) 이 거대해지지 않게.
- **`role="option"` 색·배경**: 흰 배경 + 검은 글자 + hover 시 핑크 틴트(`#FFE5EE`).

### 4.3. 콘텐츠 선택 — 검색-버튼 폼

- 키: `selected_content_ids{key_suffix}` (조회 폼) / `quick_selected_ids` (결과 페이지). **page 분기 시 콘텐츠가 바뀌면 둘 다 정리해야 일관됨.** 현재 코드는 `← 처음으로` 누를 때 `rate_*` 만 정리하고 콘텐츠 선택 키는 유지 — 이게 의도(돌아갈 때 이전 선택 유지) 인지 검토.
- 검색은 `kw in title.lower() or kw in str(id)` 단순 substring. 한글 자모 분해 검색 등은 미지원. 사용자가 “프”만 쳐도 “프리미어리그” 매칭됨.
- 매칭 결과 상위 30개 제한.

### 4.4. 메모리 (자동 메모리 시스템)

`~/.claude/projects/-Users-linazzang/memory/` :
- `MEMORY.md` 인덱스
- `project_contentsefficiency.md` (프로젝트 + 워크로그 인계 패턴)
- `feedback_work_style.md` (간결 지시 = 명시 승인)

이번 세션엔 메모리 갱신 안 함. 다음 세션에서 이 워크로그 + 메모리 같이 보면 됨.

### 4.5. gh CLI / git config

- `/tmp/gh-bin` 단일 바이너리 (이번 세션 시작 시 다시 깔았음 — 재부팅으로 사라짐).
- repo-local user.email = `lina.kwon@watcha.com`, name = `Lina Kwon`.
- push 마다 `git -c credential.helper='!/tmp/gh-bin auth git-credential' push origin main` 패턴 사용.

### 4.6. Streamlit Cloud

- 배포: https://watcha-content-efficiency.streamlit.app
- push → 자동 재배포 1~3분.
- requirements.txt 변경 시 더 오래 걸림 (이번 세션 변경 없음).
- calamine 은 옵션 (어제 워크로그 9.2). 현재 `_PRIMARY_ENGINE = "openpyxl"` + 가능 시 calamine 으로 동적 승급.

---

## 5. 막다른 골목과 재발 방지

### 5.1. 'upload' 두 번 어긋남 — 원인 미상 (대신 nuclear 우회)

4번 시도 (nowrap → 사이드바 폭 확장 → column 강제 → revert) 모두 실패. 결국 `display: none` 으로 button 자체를 숨김 (`d91af1b`).

**재발 방지**: 이런 “환경별 DOM/렌더링 차이” 깨짐은 **CSS 셀렉터 추측을 1~2번 이상 반복하지 말 것**. 추측 1회 실패 → 곧장 nuclear (element 자체 hide / 컴포넌트 교체) 로 가는 게 사용자 인내심 보호.

### 5.2. multiselect dropdown 옵션 안 보임 — 5번 실패

`role`, `data-baseweb`, body 직속 portal 등 셀렉터 추측 다 실패. **inline style 로 들어간 속성**(font-size 0 또는 transparent) 일 가능성이 높지만 검증 못함 (사용자 환경 DevTools 접근 불가, 배포 페이지는 비번 보호).

**재발 방지**:
- popover/dropdown 안 텍스트 가시성 문제는 **3번 이상 셀렉터로 안 잡히면 컴포넌트 자체를 교체**.
- multiselect 외에 다른 baseweb popover (selectbox, date input 등) 도 같은 위험. 사용자가 그쪽 깨짐 보고하면 즉시 검색-버튼 패턴으로 우회.

### 5.3. 'WATCHA' 가 화면 타이틀에 두 번 (로고 + 텍스트) → 사용자 정정

가독성 의식하지 않고 “타이틀 = 브랜드 + 기능”으로 짠 게 거슬림. **로고를 시각 식별로 쓸 때 텍스트엔 브랜드를 빼는 게 톤상 맞음** (`dd6a242`).

### 5.4. “귀엽게” 톤 = 배경 핑크가 아니다

배경은 흰톤 유지가 사용자 기준. 핑크는 액센트(버튼·도트·보더·로고 그림자) 만. 이 패턴 어제 워크로그(2026-04-28) 와 같은 결정.

### 5.5. 추정치 시각 구분은 다시 제안 X

사용자가 한 번 시도 후 즉시 거부함 (`cf7cd12`). “FLAT 예상에 추정치 포함 표시” 등 추정 관련 시각화도 같이 거부. 다음 세션에서 12절 후보 다시 제시할 때 이 항목 제외.

### 5.6. 폰트 강제 범위는 좁게

`[class*="st-"]` 같은 광범위 셀렉터는 portal/material icons/baseweb 까지 휩쓸어서 부작용이 줄줄이. **`.stApp` 안에 한정** + 필요한 곳(button/input) 만 명시.

---

## 6. 다음 세션 후보

**작은 정리**:
- [ ] 콘텐츠 선택 검색에 한글 자모 분해 매칭 (예: ‘ㅍㄹㅁㅇ’ → 프리미어리그). 지금은 substring only.
- [ ] `← 처음으로` 클릭 시 검색-버튼 콘텐츠 선택 state(`selected_content_ids` / `quick_selected_ids`) 도 같이 정리할지 결정.
- [ ] 검색어 없을 때 “최근 선택한 콘텐츠 N개” 또는 “자주 보는 콘텐츠” 같은 단축 노출.
- [ ] 매출 종류 multiselect (`2. 매출 종류 필터`) 도 사용자 환경에서 깨졌는지 확인. 깨진다면 같은 검색-버튼 패턴으로 우회.

**남은 어제 12절 후보 중 살아있는 것**:
- [ ] 2020~2024 파일 실제 테스트 — `_to_month_timestamp` 다양한 월 표기
- [ ] FLAT 예상 금액에 추정치 포함 표시 — **롤백됐으니 사용자 의사 재확인 필요**
- [ ] bill_name ↔ type 매핑 테이블
- [ ] 추정 요율 자동 추천 (다른 매출종류 / 유사 콘텐츠 평균)
- [ ] viewing_log 시청분수 트렌드 별도 뷰
- [ ] 요율 일괄 적용 / 프리셋 저장·복원
- [ ] 콘텐츠 비교 4개+ 지원 (현재 max 3)
- [ ] 차트 “급락 임계값(-30%)” 사이드바 노출 — **사이드바 비웠으니 ‘← 처음으로’ 페이지 옵션으로 위치 변경**

**이번 세션에서 새로 떠오른 후보**:
- [ ] **검색-버튼 콘텐츠 선택 UX 다듬기** — 30개 제한, 이미 선택된 항목 별도 영역 표시는 OK 하지만, 결과 버튼이 길면 스크롤 필요. 페이지네이션 또는 카테고리 필터.
- [ ] **calamine Streamlit Cloud 가용성 재확인** — 어제부터 후보. requirements 에 강제 안 넣고 계속 옵션 상태.
- [ ] **viewing_log 콘텐츠별 인덱싱 통합** — `_content_watch_minutes_by_month` 가 콘텐츠당 viewing_log 를 다시 필터링.
- [ ] **메인 업로드 영역 시각 보강** — fileUploader button 을 숨겼는데 dropzone 안이 비어 보일 수 있음. 안내 텍스트(“파일을 끌어다 놓거나 영역을 클릭”) 가 잘 보이는지 확인.
- [ ] **expander chevron 대체 마커** — chevron svg 를 숨겼으니 `▸` / `▾` 같은 텍스트 마커를 ::before 로 추가하면 펼침 상태 시각화 회복 가능.
- [ ] **결과 페이지에서 ‘콘텐츠 조회/추가’ expander 기본 펼침 여부 결정** — 현재 `expanded=False`. 사용자가 콘텐츠 자주 바꾸면 True 로.

---

## 7. 사용자 스타일 보강 (어제 10절 보강)

- **인내심 한계 신호**: “3번째 물어보고 있어”, “미친 아직도 안보이잖아”, “어떻게든 고쳐봐”. 이 말이 나오면 **추측을 멈추고 nuclear** (컴포넌트 교체 / element 자체 hide).
- **스크린샷 + 짧은 정정**이 사용자 표준 디버그 양식. 자세한 설명 X. 우리는 거기서 정확한 위치를 콕 짚어야 함.
- **opt-in 디자인 제안에 신중**: “귀엽게”·“이모지” 같은 톤 요청은 작게 시도하고 곧장 사용자 피드백. 한 번에 큰 톤 변경 → 거의 항상 정정.
- **기능 제안 시 거부 사례 즉시 메모리화**: 추정치 시각 구분이 그 예. 같은 후보 다시 제시 X.

---

## 8. 디버깅·재발 방지 메모 (어제 11절 보강)

### 8.1. ★ Streamlit baseweb popover 류는 셀렉터로 덮으려 하지 말 것
multiselect / selectbox / date_input 등 BaseWeb 기반 위젯의 dropdown 은 portal 로 mount + emotion 클래스 + virtualized list. 셀렉터 추측 1~2번 실패하면 즉시 컴포넌트 우회 (검색 input + 결과 버튼 / radio / 직접 구현).

### 8.2. ★ 광범위 `font-family !important` 는 ligature 폰트를 덮음
Material Icons / Symbols 는 ligature 키(영문 단어) 를 폰트 매핑으로 글리프 렌더. 한글 폰트로 fallback 되면 그 영어 단어 또는 비슷한 한글 글자가 그대로 텍스트로 보임 (`arrow_right`, `웹`, `일선`, `뀀`). 셀렉터 좁게 + 아이콘 폰트 영역은 글로벌 강제에서 제외.

### 8.3. ★ Plotly title=None
일부 환경에서 `"undefined"` 문자열로 변환되어 차트 위에 표시. `title={"text":"", "x":0}` 으로 명시.

### 8.4. ★ pandas Styler `applymap` deprecated (pandas 2.1+)
`DataFrame.map` 사용. 어제 추정치 시각 구분 작업 때 발견.

### 8.5. ★ Excel sheet name 31자 제한 + `[]:*?/\\` 거부
콘텐츠 라벨로 시트명 만들 때 28자 자르기 + 중복 회피 + 금지 문자 치환. `build_excel_export` 의 패턴 그대로 재사용.

### 8.6. ★ openpyxl number_format
`cell.number_format = "#,##0"`. 인덱스 컬럼은 보통 연도/날짜라 적용에서 제외 (min_col=2 부터 iter).

### 8.7. ★ st.session_state widget key 충돌
같은 위젯이 페이지 두 곳에서 렌더되면 key 충돌. `key_suffix` 패턴 사용 (조회 폼 = "" / 빠른 변경 = "_quick" 또는 별도 함수).

---

## 9. 배포·인증·git 운영 메모

### 9.1. 인증 상태
- gh CLI v2.91.0 을 `/tmp/gh-bin` (단일 바이너리). 재부팅으로 사라지면 다시 다운로드 + chmod.
- `~/.config/gh/hosts.yml` 토큰 살아있음.
- repo-local `user.email = lina.kwon@watcha.com`, `user.name = Lina Kwon`.

### 9.2. 배포 흐름
- `git -c credential.helper='!/tmp/gh-bin auth git-credential' push origin main` → Cloud webhook 자동 재배포 1~3분.
- requirements.txt 변경 없으면 빠름. 이번 세션 변경 없음.

### 9.3. force-push / amend / revert
이번 세션엔 `revert+perf` 커밋(`cf7cd12`) 가 있지만 **새 커밋으로 롤백** 한 형태 (git revert 가 아닌 코드 직접 원복). force-push / amend 없음.

---

## 10. 다음 세션 시작 시 권장 첫 단계

1. **이 문서 + `2026-04-28-...` + `2026-04-27-...` + `2026-04-23-...` 모두 훑기**.
2. `cat ~/.claude/projects/-Users-linazzang/memory/MEMORY.md` 로 메모리 인덱스 확인.
3. `git log --oneline -30` 로 새 커밋 확인 (이번 워크로그 자체 커밋이 마지막일 것).
4. **gh CLI 살아있는지** `ls -la /tmp/gh-bin` (단일 바이너리). 없으면 9.1 절 절차로 재설치.
5. **repo-local git config** 확인.
6. **로컬 환경 복원**: `cd ~/Projects/contentsefficiency && .venv/bin/streamlit run app.py`.
7. **배포 앱** https://watcha-content-efficiency.streamlit.app HTTP 303 확인.
8. 사용자에게 6절 후보 목록 검토 요청. 단, 5.5 절(추정치 시각 구분 거부) 과 5.4 절(배경 핑크 거부) 은 메모리에서 제외.

---

## 11. 부록 — 이번 세션의 사용자 메시지 흐름 (요약)

- “저번 작업 이어서 할게” → 메모리 + 워크로그 12절 후보 표 제시
- “기능 추가의 1·2·3번 하자” → `2e4ea73`
- “추정치 구분 및 표시는 안해도 될거 같아 그것만 되돌려줘” → `cf7cd12` (롤백 + perf 캐시)
- “콘텐츠별 상세 탭에 연간 합계와 연간 평균” → `d92e325`
- “1000단위 구분기호” → `5b3c7e3`
- “디자인을 좀 더 귀엽게” → `81b39e0`
- “배경색 너무 핑크야;; 원래 색으로 돌려줘” → `52cf8cf`
- “WATCHA는 빼도 될거 같아” → `dd6a242`
- “지금 적용된 폰트는?” / “Apple SD 산돌고 Neo” → `684784a` (이후 모든 깨짐의 시작)
- 'upload' 두 번 / `웹`/`일선` / `뀀` / 도움말 깨짐 사투 → `a9a5763` ~ `d91af1b` (8커밋)
- “화면 구성 순서를 바꿔보자” → `1657d76` (페이지 분리)
- “이모지 깨짐 / NaN” → `1da3d10`
- “expander 옆 _arrow_right / 차트 undefined” (PDF 첨부) → `67fec84`
- dropdown 옵션 안 보임 5연쇄 → `4932c9c`, `cfebcea`, `8b5c017`, `a976b41`, `3938522`
- “미친 아직도 안보이잖아 제발 어떻게든 고쳐봐” → `cdc53d3` (multiselect 자체 교체)
- “워크로그 작성하자.” → 본 문서

각 요청마다 **추가 컨텍스트 질문 없이 즉시 구현·푸시**가 표준 (어제·그저께와 동일). 다만 폰트 깨짐 디버깅 단계에서 **추측 셀렉터 박기 + 푸시 + 사용자 재테스트** 사이클이 6~8회 반복됨. 다음 세션은 같은 패턴 반복 X — 1~2회 시도 후 nuclear.
