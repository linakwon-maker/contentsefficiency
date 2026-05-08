# 2026-05-08 · 검색 범위 확장(viewing_log/sales_log) + 월별 상세 trailing 잘라내기

> **작성 목적**: 9일 만에 이어진 세션. 마지막 작업은 2026-04-29 저녁 워크로그(`617504b`).
> 이번 세션은 작은 cleanup 1 + 기능 보강 2, 총 3 커밋. app.py **+58줄 (2117 → 2175)**.
>
> 이전 워크로그: `2026-04-23`, `2026-04-27`, `2026-04-28`, `2026-04-29-feature-then-font-and-multiselect-rework.md`, `2026-04-29-evening-review-refactor-and-ux-polish.md`. 이 문서는 마지막의 후속.

---

## 0. TL;DR — 3 커밋 요약 (시간순)

| # | 해시 | 메시지 | 핵심 |
|---|------|--------|------|
| 1 | `81a626b` | docs: 모듈 docstring 1~3 → 1~5 동기화 | `a80e159` 에서 5-cap 확장했지만 `app.py` 모듈 docstring 만 누락 |
| 2 | `0d0568a` | feat(search): viewing_log/sales_log 의 콘텐츠도 검색 목록에 포함 | RS 정산 행이 없는 콘텐츠(예: FLAT 라이센스만 있는 작품)가 대시보드 검색에서 사라지던 문제 해결 |
| 3 | `708e70a` | ux(monthly): 월별 상세 비교를 마지막 매출 발생 월까지로 잘라내기 | 표 끝에 trailing 0/NaN 행이 길게 늘어지던 현상 제거. 중간 0 행은 유지 |

---

## 1. 시작 상태

- 마지막 커밋: `617504b` (저번 워크로그 그 자체).
- 작업 트리 깨끗, branch up to date.
- 최근 워크로그 6절 “다음 세션 후보” 중 사용자가 **즉시 cleanup — docstring 동기화** 부터 선택.
- 환경: macOS, .venv/bin 활성화 가능, 배포 https://watcha-content-efficiency.streamlit.app 살아있음.

---

## 2. 사용자 요구 (시간 순)

1. “linakwon-maker/contentsefficiency 프로젝트를 이어서 수정하고 싶어”
   → 후보 4개 제시(차트 팔레트 5색 / 카드 grid 마지막 행 / docstring 동기화 / expander 시각 보강) → 사용자가 **docstring 동기화** 선택
2. “왜 특정 콘텐츠는 검색했을 때 조회가 안될까? 예를 들어 1567308, 상견니를 엑셀 파일에서 직접 입력하면 나오는데 대시보드에서는 조회가 안돼”
   → 디버깅 진행. confidential 시트만 본다는 점 발견. “confidential 에서 내가 id 를 직접 입력했어” 보강 → “**confidential 에 검색 내역이 없어도 조회할 수 있게 해줘 viewing_log, sales_log 값에서 매칭해서**”
3. “좋아 이번엔 월별 상세 비교에서 마지막으로 매출이 나온 월까지만 값을 보여줘”
4. “좋아 워크로그 작성해줘”

각 요청 즉시 구현 → commit → push 사이클. 정정 사이클 거의 없음(짧은 대화).

---

## 3. 작업 정리

### 3.1. docstring 동기화 (`81a626b`)

`a80e159` (콘텐츠 5-cap) 에서 sidebar caption / hint / full 판정 / 컬럼 grid 까지 모두 동기화했지만 **`app.py` 최상단 모듈 docstring 만 1~3 그대로** 였음. 1글자 변경.

```diff
-콘텐츠 ID 1~3개 + 매출 종류 필터를 지정하면 2020~2026 월별 매출을
+콘텐츠 ID 1~5개 + 매출 종류 필터를 지정하면 2020~2026 월별 매출을
```

→ 워크로그 6절 “즉시 cleanup” 첫 항목 소진.

### 3.2. 검색 범위 viewing_log / sales_log 로 확장 (`0d0568a`)

**문제**: 사용자가 1567308(상견니) 을 대시보드 검색창에 입력해도 결과 없음. 엑셀에선 confidential 시트에 행 있음(사용자 직접 확인). RS 정산 행이 없는 콘텐츠는 검색 목록에 누락.

**원인 분석 (systematic-debugging Phase 1~3)**:
- `extract_all_contents` 가 `_read_content_sheet` (= `_read_confidential_sheet`) 만 훑음
- viewing_log / sales_log 의 `content_id` 컬럼은 무시됨
- 사용자 케이스에서는 confidential 의 헤더 detect 가 잘못 됐을 가능성도 있었지만 (이건 진단 미완), 사용자가 **요구를 일반화** — “confidential 에 없어도 다른 시트에서 조회”

**구현**:
- `_absorb_id_title_pairs(seen, df)`: DataFrame 받아 (id, title) 쌍 vector 추출 후 seen dict 에 병합 — 공통 로직 분리
- `_log_sheet_id_title_pairs(data, keyword)` (`@st.cache_data`): viewing_log / sales_log 시트에서 **id + title 컬럼만 `usecols` 로 읽음** (메모리·시간 절약). title 부재 시 `(id, "")` 형식
- `extract_all_contents`: `confidential ∪ viewing_log ∪ sales_log` 합집합 반환

**결정 — 왜 `_read_log_sheet` 재사용 안 했나**: 그 함수는 모든 컬럼을 읽음. viewing_log 는 수백만 행 가능 — id/title 만 필요한 검색 list 빌드에는 과함. 별도 cached read 로 분리.

**결정 — 왜 lazy 안 했나**: “검색 결과 없을 때만 log 시트 검색” 같은 fallback 도 가능했지만 UI 흐름 복잡해짐. 캐시 한 번 빌드 = 영구 hit 라 acceptable. 성능 문제 발견 시 lazy 전환 검토.

**제목 없을 때**: viewing_log/sales_log 에 title 컬럼이 없으면 `(id, "")` 로 들어감 → 사용자는 **ID 로만** 검색 가능. 제목 검색 원하면 confidential 에 있어야 함. 사용자 보고 후 실제 동작 확인 예정.

### 3.3. 월별 상세 비교 trailing 잘라내기 (`708e70a`)

**증상**: 월별 상세 비교 표 끝에 0 / NaN 만 있는 행이 길게 늘어짐 (예: 오늘이 2026-05 인데 2026-12 까지 빈 행 노출).

**규칙**:
- “마지막으로 매출이 발생한 월” = 어떤 콘텐츠든 0 도 NaN 도 아닌 매출이 잡힌 마지막 period
- 그 월까지 잘라 표시
- **중간 0 행은 유지** (런칭 후 일시 휴지기 등 의미 있을 수 있음)
- **엑셀 export 의 “월별 상세” 시트는 그대로** (raw 데이터 보존, 재가공 여지)

**구현 (3줄)**:
```python
nonzero = pivot.fillna(0).ne(0).any(axis=1)
if nonzero.any():
    last_period = nonzero[nonzero].index[-1]
    pivot = pivot.loc[:last_period]
```

mini repro 로 검증: `[100, 200, 0, NaN, NaN]` + `[50, 0, 0, 0, 0]` → `2024-02` 까지만 남고 2024-03~05 잘림. ✓

---

## 4. 디버깅·결정사항 메모

### 4.1. ★ pandas usecols 로 메모리 아끼기

`pd.read_excel(..., usecols=[id_col, title_col], dtype=str)` — 컬럼 부분만 읽고 타입 추론 끔. 큰 시트(50MB+ × 수백만 행)에서 search list 빌드용으로 유용. 헤더만 미리 보려면 `nrows=0` 으로 dtypes 만 받는 트릭.

### 4.2. ★ trailing zero/NaN 잘라내기 패턴

```python
nonzero = pivot.fillna(0).ne(0).any(axis=1)
if nonzero.any():
    last_idx = nonzero[nonzero].index[-1]
    pivot = pivot.loc[:last_idx]
```
- `fillna(0).ne(0)`: NaN 도 0 도 아닌 값 = True
- `.any(axis=1)`: 행 단위 OR 집계
- `nonzero[nonzero].index[-1]`: 마지막 True 의 라벨
- `loc[:last_idx]`: label 기반 inclusive slice

index 가 sorted 인 게 전제. `period` 가 `"YYYY-MM"` zfill 이라 lex = chrono 정렬 일치.

### 4.3. ★ extract_all_contents 캐시 키 재빌드

함수 본문 변경 시 Streamlit cache_data 가 자동 invalidate (소스 hash). 배포 첫 호출에서 cache rebuild → 이후 hit. 사용자에게 “1~3분 안에 재배포” 후 첫 검색이 살짝 느릴 수 있음을 명시 안 했지만 통상 cold start 범위.

### 4.4. ★ systematic-debugging skill 적용

“상견니 안 나옴” 받았을 때 바로 fix 안 가고:
1. `extract_all_contents` 정의 읽음
2. `_read_content_sheet` → `_read_confidential_sheet` 체인 확인
3. ID/TITLE 컬럼 후보, header detect, ID 정규화(`\.0$` strip) 검토
4. 가설 4개 정리(H1: log 전용, H2: float ID 형식, H3: header 잘못, H4: 다른 파일)
5. 사용자 추가 정보(“confidential 에 직접 입력으로 발견”) 받고 H1 후퇴
6. 진단 스크립트 제안하려는 차에 사용자가 **요구를 일반화** → fix 방향 확정

→ Phase 2 ‘pattern analysis’ 직전에 사용자가 결정. 디버깅 완료까지 안 갔지만 가설을 근거로 좁혔다는 점이 random fix 와 다름.

---

## 5. 다음 세션 후보

**저번 워크로그 6절에서 아직 남은 후보**:
- [ ] `flat_depreciation` 값을 `_go_to_query_page` 에서 정리할지 결정 (보존 중)
- [ ] `selected_content_ids{suffix}` 도 ← 처음으로 시 정리할지 검토 (보존 중)
- [ ] B1~B4, R1~R10, P2(`compute_flat_estimates` cache), P4(future_stack), P11
- [ ] 2020~2024 파일 실제 테스트 — `_to_month_timestamp` 다양한 월 표기
- [ ] bill_name ↔ type 매핑 테이블
- [ ] 추정 요율 자동 추천 (다른 매출종류 / 유사 콘텐츠 평균)
- [ ] viewing_log 시청분수 트렌드 별도 뷰
- [ ] 요율 일괄 적용 / 프리셋 저장·복원
- [ ] 차트 “급락 임계값(-30%)” 본문 노출
- [ ] calamine Streamlit Cloud 가용성 재확인
- [ ] 차트 팔레트 5색 확장 (현재 3색 반복)
- [ ] 합계 카드 5칸 grid 마지막 행이 1~2개일 때 정렬
- [ ] 감가 계수 변경 시 spinner
- [ ] 콘텐츠별 상세 expander chevron / hover 시각 보강

**이번 세션에서 새로 떠오른 후보**:
- [ ] **viewing_log/sales_log 만 있는 콘텐츠는 제목 없이 ID 만 보임** — 검색 결과 표시에 “(제목 없음)” 라벨 추가 또는 confidential 보강 로직(예: 다른 연도 파일에서 title 가져오기) 검토
- [ ] **엑셀 export ‘월별 상세’ 시트도 잘릴지 결정** — 사용자가 동일 동작 원하면 export 측에도 동일 truncate 적용
- [ ] **차트(`render_comparison_chart`)·연간 합계도 trailing 잘라내기** — 일관성. 단 차트는 `plot_df` 가 long format 이라 별도 truncate 필요
- [ ] **상견니(1567308) 검색이 실제로 되는지 확인** — viewing_log/sales_log 에 ID 가 있는지, 컬럼명이 `content_id` 인지 검증. 안 되면 진단 스크립트로 시트 구조 보기

---

## 6. 다음 세션 시작 시 권장 첫 단계

1. **이 문서 + 4-29 두 워크로그 + 4-28 / 4-27 / 4-23 훑기**.
2. `cat ~/.claude/projects/-Users-linazzang/memory/MEMORY.md` 인덱스 확인.
3. `git log --oneline -10` (이번 워크로그가 마지막).
4. **gh CLI** `ls -la /tmp/gh-bin` (재부팅으로 사라질 수 있음).
5. **로컬 환경**: `cd ~/Projects/contentsefficiency && .venv/bin/streamlit run app.py`.
6. **배포 앱** https://watcha-content-efficiency.streamlit.app HTTP 확인.
7. **상견니 검색 실제 동작 확인** — 5절 “이번 세션에서 새로 떠오른 후보” 마지막 항목.

---

## 7. 부록 — 사용자 메시지 흐름 (요약)

- “이어서 수정하고 싶어” → 후보 4개 제시 → **docstring 1~3 → 1~5** 선택 → `81a626b`
- “1567308, 상견니 검색 안 돼” → systematic-debugging Phase 1~3 → 사용자 “confidential 에서 직접 id 입력해 발견” → 가설 후퇴 → 사용자 “confidential 에 없어도 viewing_log/sales_log 에서 매칭” → `0d0568a`
- “월별 상세 비교 마지막 매출 월까지만” → trailing 0/NaN 잘라내기 → `708e70a`
- “워크로그 작성해줘” → 본 문서

각 요청마다 **추가 컨텍스트 질문 거의 없이 즉시 구현·푸시**. 디버깅 단계만 사용자에게 시트 위치 한 번 물어봄(사용자가 “명료화 필요” 응답으로 reroll 요청 → 결국 정보는 다음 메시지에서 직접 공유).
