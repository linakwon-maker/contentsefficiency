# 2026-04-23 · 콘텐츠 매출 분석 MVP 초기 구축 및 배포

> **작성 목적**: 다음 세션에서 이 프로젝트를 이어 작업할 때 빠르게 맥락을 복구할 수 있도록 오늘 결정한 내용·설계 근거·숨은 제약을 가능한 한 자세히 남김. 코드는 git에서 볼 수 있으니 **"왜 이렇게 했는가"** 중심.

---

## 1. 프로젝트 개요

### 1.1. 배경 · 요구사항
- **사용자**: 왓챠 콘텐츠 수급 담당자 (lina.kwon@watcha.com)
- **업무 맥락**: 플랫폼 내 콘텐츠의 **시청분수·매출·유입기여도(AVS)** 등을 보고 수급 효율을 판단. 지금까지는 매번 연도별 구글 시트(혹은 엑셀)를 열어 수작업으로 대조해야 해서 번거로웠음.
- **MVP 요구사항**
  - 콘텐츠 ID 입력 → 2020~2026 연도별·월별 매출을 한 눈에
  - 연도별 합계·평균 + 월별 상세
  - 매출 급락 시각화
  - 콘텐츠 **최대 3개 동시 비교**
- **확장 예정 (MVP 이후)**: 대시보드 데이터 연동 (유입기여도 AVS, 시청분수, 가입·해지 기여도 등)
- **제약**: 이 세션에서 2시간 안에 **완성 + 배포**. 팀원과 바로 공유 가능해야.

### 1.2. 기술 스택 (최종)
- **UI/서버**: Streamlit 1.50
- **데이터 처리**: pandas 2.x, openpyxl 3.x
- **시각화**: plotly 6.x (line chart + 급락 마커)
- **언어**: Python 3.9 (로컬), Streamlit Cloud는 3.11+ (배포 환경)
  - `from __future__ import annotations` 로 3.9 호환 유지 (`list[str] | None` 같은 신문법도 런타임 평가 안 됨)
- **배포**: Streamlit Community Cloud
- **저장소**: https://github.com/linakwon-maker/contentsefficiency (**현재 public**, 하단 7.1 주의 참조)

### 1.3. 배포 URL
- **앱 URL**: https://watcha-content-efficiency.streamlit.app
- **비밀번호**: Streamlit Cloud Secrets 의 `app_password` 값으로 설정됨
  - 구체 값은 Streamlit Cloud 대시보드 → 앱 Settings → Secrets 에서 확인 가능
  - 로컬에서는 `.streamlit/secrets.toml` 에 동일하게 저장 (gitignore)

---

## 2. 최초 설계 결정 (Phase 0~1)

### 2.1. "구글 시트 자동 접근" → "엑셀 업로드" 로 피벗
원래 구글 시트 + 서비스 계정 + Streamlit Secrets 방식으로 설계했음 (`gspread` + `google-auth` 사용). 하지만 실제로 준비하려 하니:
- 왓챠는 기존 GCP 프로젝트가 있고 유관부서 승인이 필요 → 2시간 MVP에 현실적으로 맞지 않음
- 서비스 계정 키 발급이 조직 정책으로 막혀있을 가능성
- Streamlit Cloud (외부 SaaS) 에 사내 기밀 데이터 자동 접근 권한을 두는 것에 보안팀 검토 필요

**사용자 판단**: "대공사다. 엑셀 파일로 바로 줄게" → 구글 시트 자동 접근은 포기.

**전환 후 장점**:
- GCP 설정·보안팀 승인 **불필요**
- 매출 데이터가 **코드/Secrets/GitHub 어디에도 저장되지 않음** (사용자가 세션마다 업로드, 서버 메모리에만)
- 접근 통제가 "앱 비밀번호 + 엑셀 파일" 이중 잠금 구조로 훨씬 간단해짐

**의존성 변화**:
- 제거: `gspread`, `google-auth`, `google-auth-oauthlib`, `requests-oauthlib`, `oauthlib`
- 추가: `openpyxl`

### 2.2. 파일 업로드 방식 결정
사용자가 "연도별로 파일이 7개 분리" 형태라고 확인.
- `st.file_uploader(accept_multiple_files=True)` 로 여러 파일 동시 업로드
- **파일명에서 4자리 연도 자동 추출** (정규식 `(20\d{2})`) → `2020.xlsx`, `sales_2023.xlsx`, `2025_콘텐츠매직시트.xlsx` 모두 OK
- 업로드된 파일은 `st.session_state["file_datas"]` 에 `list[(filename, bytes)]` 로 저장 → 재실행 시에도 재업로드 불필요

### 2.3. 보안 모델
```
사용자 접속 → 비밀번호 게이트 (watcha2026!) → 엑셀 업로드 → 매출 조회
             ↑                              ↑
             Streamlit Secrets에 저장       사용자가 매번 직접 공급
                                            (서버에 영구 저장 X)
```
- 비밀번호 게이트: `st.secrets["app_password"]` 체크. 세션 단위 `st.session_state["authed"]`.
- 매출 데이터: **절대 앱 코드/Secrets/GitHub 에 올리지 않음**. `.gitignore` 에서 `.streamlit/secrets.toml` 명시 차단, 실제 데이터는 업로드 파일 메모리에만.

---

## 3. 왓챠 "콘텐츠 매직시트" 엑셀 구조 (중요)

### 3.1. 실제 파일 분석 결과 (2025_콘텐츠매직시트.xlsx 기준)
파일 하나에 **시트(탭)가 5개** 있음:
| 시트명 | 내용 | 앱에서 사용? |
|--------|------|-------------|
| **`Confidential`** | ✅ **실제 매출 데이터 (2,254행)** | **O** (우선 선택) |
| `viewing_log` | 에피소드별 시청 원시 로그 | X |
| `sales_log` | 매출 종류별 총합(콘텐츠ID 없음) | X |
| `for_episode` | 에피소드별 계산용 가이드 | X |
| `guide` | 빈 시트 | X |

### 3.2. `Confidential` 시트 구조
- **상단 0~3행은 메타데이터**: "*Confidential" 경고, 전체 시청분수 요약, 빈 행 등
- **실제 헤더는 5번째 행 (index 4)**: `type | category | id | title | 매출 종류 | 요율 | note | 2025-01-01 | 2025-02-01 | ... | 2025-12-01 | 평균 | 감가 | FLAT예측금액 | FLAT예측금액2`
- **실제 데이터는 6번째 행부터** (index 5+)
- **월별 컬럼은 datetime 형식** (`datetime.datetime(2025, 1, 1, 0, 0)` 등)
  - ⚠️ **2025년 파일의 10월 컬럼만 문자열** `'2025.10. 01'` (점 구분자 + 공백)로 들어있음. 다른 연도도 유사한 변형 가능성 있어 월 파싱 로직을 구분자(`-`, `.`, `/`, `년`) + 공백 유연하게 처리하도록 구현했음 (`_extract_month()`).

### 3.3. 데이터 구조의 특이점 — 같은 콘텐츠가 여러 행으로 쪼개짐
한 콘텐츠(예: `3338924` 시맨틱 에러)가 **여러 행**으로 존재:
```
type=시청분수         · 매출 종류=NaN   · 요율=NaN   → 시청 분수 raw (원 단위 X)
type=정산금(rs기준)   · 매출 종류=B-1  · 요율=0.5   → 실제 매출 (원)
type=시청분수         · 매출 종류=B-1  · 요율=1     → (이건 왜 있는지는 정확히 모름, 점유율성 지표로 추정)
```
다른 콘텐츠는 여러 개의 매출 종류(B-1, B-2, B-3J, B-4, B-4L, B-5, B-5K, C-2, E-1 등) 행을 가질 수 있음. 이건 각 콘텐츠가 여러 매출 계약 조건(플랜/상품/계약)을 동시에 가질 때 발생.

### 3.4. "월별 매출" 계산 방식 (사용자와 확정)
**질문**: 같은 콘텐츠의 여러 행을 어떻게 합산하여 "월별 매출"로 표시할까?
**사용자 결정**: `type = 정산금(rs기준)` 행들만 집계하되, **사이드바에 매출 종류 멀티셀렉트 필터**를 두어 원하는 매출 종류(B-1, B-2 등)만 골라 합산 가능. 기본은 전체 선택.
- 구현 위치: `load_sales_from_uploads()` 내 `working[working[type_col] == "정산금(rs기준)"]` 필터 + `working[working[cat_col].isin(selected_categories)]` 필터.
- 같은 콘텐츠의 여러 (매출 종류) 행은 `pivot_table(aggfunc="sum")` 으로 자동 합산.

### 3.5. 연도별 파일 구조 — 사용자 확언
사용자 확인: "모든 연도가 같은 템플릿 (Confidential 시트, 같은 헤더 위치)". 따라서 2025년과 동일한 파싱 로직을 다른 연도에도 적용할 수 있을 것으로 가정. **다만 실제 2020~2024 파일로는 아직 검증 안 됨** (다음 세션에서 확인 필요. 특히 10월 포맷 같은 소소한 변형이 있을 수 있음).

---

## 4. 구현된 기능 (커밋별)

### Commit `18e68d9` — MVP 초기 버전
- 엑셀 업로드, 비밀번호 게이트, 콘텐츠 ID 3개 수동 입력, 연×월 피벗, 라인 차트, 매출 급락(-30%↓) 빨간 X 마커
- **컬럼 자동 감지 로직** (`_find_column`, `_find_month_columns`)
  - ID 후보: `id`, `content_id`, `contents_id`, `콘텐츠 ID` 등
  - 제목 후보: `title`, `content_title`, `제목` 등
  - 월 컬럼: datetime, ISO 문자열, `1월`, `Jan`, `1` 등
  - `type` 후보, `매출 종류` 후보도 같은 방식으로 감지
- 헤더 자동 감지(`_find_header_row`): 상단 15행 중 `{id, title, type, category, 콘텐츠id, 매출종류}` 키워드가 2개 이상 보이는 행
- 시트 우선순위(`_pick_best_sheet`): `confidential` > `매출` > `sales` > `revenue` > 첫 시트
- `@st.cache_data(ttl=300)` 캐시 (엑셀 파싱은 무거우니)

### Commit `9b8d339` — 콘텐츠 동시 비교 뷰로 UI 개편
사용자 피드백: "각 콘텐츠의 연도별 매출을 **따로** 보여주는 것 같은데 한 페이지에서 **같이** 비교하고 싶다" → 탭 구조 폐기.

**새 레이아웃**:
1. "비교 콘텐츠: 📺 A · 📺 B · 📺 C" 한 줄 요약
2. **📈 매출 추이 비교** (라인 차트, 상단)
3. **📋 연간 합계 비교** (행=연도, 열=콘텐츠)  — `render_yearly_comparison()`
4. **📋 월별 상세 비교** (행=연-월, 열=콘텐츠, 스크롤 400px) — `render_monthly_comparison()`
5. **🔍 콘텐츠별 상세** (expander 기본 닫힘, 필요시 펼침)

### Commit `5361450` — 콘텐츠 제목으로 검색 가능한 드롭다운
사용자 요청: "시트의 E열(제목)로도 검색 가능하게" → ID 텍스트 입력 3개를 검색 가능한 multiselect 1개로 교체.

**새 함수**: `extract_all_contents(file_datas)` — 업로드된 파일들에서 모든 `(id, title)` 페어 수집 (중복 제거, 제목 있는 쪽 우선). 제목 가나다순 정렬.

**UX**: `st.multiselect(max_selections=3)` 옵션으로 `"제목 (ID)"` 형태 표시. 사용자가 타이핑하면 실시간 필터. 2025 파일 기준 **1,068개 콘텐츠** 풀에서 검색 가능.

---

## 5. 배포 과정에서 겪은 시행착오

### 5.1. Python 3.10+ 문법 → 3.9 호환
처음 `list[str] | None` 같은 3.10+ 문법을 썼는데 로컬 Python이 3.9였음.
- 해결: `from __future__ import annotations` 추가 → 타입 힌트가 문자열로 지연 평가됨.
- Streamlit Cloud 는 3.11+ 환경이라 배포 시 경고 사라짐.

### 5.2. gh CLI 설치 (brew 없이)
사용자 머신에 brew, gh, GitHub Desktop 모두 없었음. GitHub HTTPS 인증용 credential도 없었음.
- 해결: gh 공식 릴리즈 zip 다운로드 → `/tmp/gh/` 풀어서 `/tmp/gh-bin` 심볼릭 링크.
- `gh auth login --hostname github.com --git-protocol https --web --skip-ssh-key` 에 `printf '\n\n\n'` 으로 기본 Enter 먹이고 background 실행.
- device code (`6234-267E` 등) stdout에서 꺼내서 사용자에게 전달 → 브라우저 로그인 → `gh auth setup-git` → `git push` 정상.
- ⚠️ **다음 세션에서는 gh가 `/tmp/gh-bin` 에 없음** (임시 폴더라 리부트 시 사라짐). 필요하면 재설치하거나 정식 설치(`brew install gh`) 고려.

### 5.3. Streamlit Cloud `This repository does not exist`
처음에 비공개 repo로 만들었는데 Streamlit Cloud가 못 봄.
- 원인: Streamlit GitHub App에 private repo 접근 권한이 없음
- 선택지 2개: (A) GitHub Apps 설정에서 권한 추가 (B) repo를 public으로 전환
- 사용자 **명시적 승인** 하에 (B) 선택: `gh repo edit --visibility public --accept-visibility-change-consequences`
- ⚠️ **보안상 주의**: 하단 7.1 참조

### 5.4. Streamlit Cloud Secrets 누락
배포는 됐는데 Deploy 시점에 Secrets 탭 저장을 안 해서 앱이 "`app_password` 가 설정되지 않았습니다" 에러. 사용자가 대시보드 → Settings → Secrets 탭에 직접 저장.
- ⚠️ **Streamlit Cloud Secrets는 CLI/API 수정 불가** (웹 UI 전용). 다음 세션에서도 Secrets 변경하려면 사용자가 직접 클릭 필요.

### 5.5. Streamlit Cloud "Who can view this app"
기본이 "Only specific people" 이라 팀원도 Streamlit 로그인 필요한 상태였음. Sharing 탭에서 **"This app is public and searchable"** 로 전환.
- 실제 브라우저 접속은 되는데 `curl` 은 여전히 303 리다이렉트 (Streamlit이 자동화 트래픽을 User-Agent/쿠키/TLS fingerprint 기반으로 다르게 처리하는 듯).
- 헬스체크 시 주의: `curl` 결과만으로 "막혔다"고 판단하면 안 됨. 브라우저 접속 확인이 최종.

---

## 6. 최종 코드 구조 (app.py, 671줄)

```
app.py
├── (L1-40)    설정 · 상수 (YEARS, 컬럼 후보 리스트, REVENUE_TYPE_VALUE="정산금(rs기준)")
├── (L43-78)   require_password()           — 비밀번호 게이트
├── (L81-170)  유틸 · 컬럼 자동 감지
│   ├── _normalize(s)                      — 공백 제거 + 소문자
│   ├── _find_column(cols, candidates)
│   ├── _extract_month(col)                — datetime/ISO/한글/영문/숫자 월 추출
│   ├── _find_month_columns(cols)
│   ├── _to_number(value)                  — 매출 셀 → float
│   └── _detect_year_from_filename(name)
├── (L173-225) 엑셀 파싱
│   ├── _pick_best_sheet(sheet_names)      — Confidential 우선
│   ├── _find_header_row(raw)              — 헤더 행 자동 감지
│   └── _read_content_sheet(data)          — 캐시됨 (@st.cache_data)
├── (L228-290) 콘텐츠/매출종류 추출 (사이드바용)
│   ├── extract_all_contents(file_datas)   — 1,068개 수준 콘텐츠 목록
│   ├── _format_content_option(c)          — "제목 (ID)" 형식
│   └── extract_sales_categories(file_datas)
├── (L293-390) load_sales_from_uploads()   — 메인 데이터 로딩. long format 반환
├── (L393-490) 렌더링 함수들
│   ├── render_pivot(df)                   — 연×월 피벗 (연간 합계/평균 포함)
│   ├── render_yearly_summary(df)          — 연도별 st.metric 카드
│   ├── _content_labels(df, ordered_ids)   — {id: "제목 (ID)"} 사전
│   ├── render_yearly_comparison(df, ids)  — 연도×콘텐츠 비교 표
│   ├── render_monthly_comparison(df, ids) — 연-월×콘텐츠 긴 표
│   └── render_comparison_chart(df)        — Plotly 라인 + 급락 X 마커
└── (L493-671) main()
    ├── require_password()
    ├── 사이드바: 1.파일업로드 / 2.매출종류필터 / 3.콘텐츠선택(multiselect)
    └── 메인: 비교 콘텐츠 요약 → 라인차트 → 연간 합계 비교 → 월별 비교 → 콘텐츠별 상세(expander)
```

### 중요한 코드 규약
- **secrets 접근은 항상 try/except** — secrets.toml 없을 때도 비밀번호 에러 화면 띄우게.
- **월 컬럼 파싱은 유연하게** — `_extract_month()` 하나로 모든 형식 처리. 새 연도 파일에서 새 변형이 나올 수 있으니 이 함수 확장 포인트.
- **ID 문자열 정규화**: `str(x).strip()` 후 `.0$` 제거 (엑셀에서 숫자 ID가 `"3338924.0"` 으로 저장되는 경우 대응).

---

## 7. 다음 세션을 위한 컨텍스트

### 7.1. ⚠️ 보안: repo가 현재 public 상태
- 2시간 MVP 시간 제약 때문에 private → public 전환했음 (사용자 명시적 승인)
- 노출되는 것: 왓챠 매직시트 파싱 로직, "정산금(rs기준)" 등 사내 컬럼명, 매출 종류 코드(B-1 등)
- **노출 안 되는 것**: 실제 매출 데이터, 콘텐츠 제목 목록, 비밀번호
- 여유 있을 때 되돌릴 옵션:
  - A. Private 복귀 + Streamlit GitHub App에 `contentsefficiency` repo 접근 권한 부여 (`https://github.com/settings/installations` → Streamlit → Configure)
  - B. 사내 사내배포(BigQuery/AWS 등)로 이전 + Streamlit Cloud 제거

### 7.2. 아직 검증 안 된 것
- **2020~2024 연도 파일 파싱** — 사용자는 "동일 템플릿"이라 했지만 2025 이외는 실제 업로드 테스트 안 됨. 10월 같은 특이 변형이 추가로 있을 수 있음. 문제 생기면 `_extract_month()` 와 `_find_header_row()` 를 우선 확인.
- **매출 종류(B-1 외)** 합산 정합성 — 2025 파일에선 B-1만 쓰였는지 B-1/B-2/B-5 3개만 추출됨. 다른 연도에는 더 다양할 수 있음.
- **동시 사용자 부하** — Streamlit Community Cloud 무료 플랜은 리소스 제한 있음 (1GB 메모리 등). 팀 전체가 동시에 12MB 엑셀 7개 업로드하면 느려질 수 있음.

### 7.3. 확장 예정 (사용자가 처음 언급한 방향)
- **대시보드 데이터 연동** — 유입기여도(AVS), 총 시청분수, 가입·해지 기여도. 매직시트의 `viewing_log` 시트에 시청 로그가 있음. 또는 별도 대시보드 API.
- **콘텐츠 인사이트 자동 요약** — "이 콘텐츠는 2024년 7월 이후 매출이 60% 하락했습니다" 같은 자연어 요약 (Claude API 연동 가능).

### 7.4. 당장 떠오르는 개선 아이디어
- 피벗 테이블 **엑셀 다운로드 버튼** (`st.download_button`)
- 급락 임계값 `-30%` 를 사용자가 사이드바에서 조절
- **제목 여러 개 부분일치** → 현재 multiselect 는 완전 매치 옵션 클릭 필요. 텍스트 자유 검색 + 후보 자동추천 모드 추가해도 좋음.
- 데이터 없는 달 표시: 현재는 `-` 로 표시 (NaN). 0으로 해석할지 "미집계"로 해석할지 명확히 구분
- 라인 차트에 **연도 경계 세로선** 추가 (시각적 구분)
- **콘텐츠별 최고/최저 매출 월** 하이라이트
- 모바일 반응형 (현재 layout="wide"는 큰 화면 전제)

### 7.5. 환경 상태
- 로컬 venv: `/Users/linazzang/Projects/contentsefficiency/.venv/` (Python 3.9, streamlit/pandas/plotly/openpyxl)
- 로컬 Streamlit 서버: 세션 중 background (task id `bzrn9vkdi`)로 돌아있었음. 다음 세션에서는 종료되어 있을 가능성 높음. 필요하면 `.venv/bin/streamlit run app.py` 재실행.
- gh CLI: `/tmp/gh-bin` (임시). 리부트 시 사라짐.
- `git config` 는 repo 로컬에만 `user.email="lina.kwon@watcha.com"`, `user.name="Lina Kwon"` 세팅. 전역은 건드리지 않음.

### 7.6. 참고: 초기 계획 문서
- `/Users/linazzang/.claude/plans/ott-snuggly-porcupine.md` — 최초 수립한 2시간 MVP 구현 계획. 그 계획은 **구글 시트 기반**이었으나 도중에 엑셀 업로드 방식으로 피벗됐음. 배경 참고용.

---

## 8. 주요 사용자 지시 · 선호사항

- 언어: 한국어만 사용 (CLAUDE.md 지침)
- 설명: **비개발자 친화** 톤 (일상 비유 + 맥락 + 추천 근거). 기술 용어는 쉬운 말로 풀어서.
- 결정: 여러 옵션 제시할 땐 **언제 뭐가 좋은지 맥락**과 **최종 추천**까지 명확히.
- 작업 스타일: 빠른 이터레이션 선호. "얌마 너 뭐해 gh로 니가 해" 같은 직설적 피드백에 바로 반응하기. 불필요한 확인 최소화 (auto mode).

---

## 9. 커밋 이력 (시간순)

| 해시 | 메시지 | 주요 변경 |
|------|--------|----------|
| `18e68d9` | feat: 콘텐츠 매출 분석 MVP 초기 버전 | app.py 전체, requirements, README, gitignore, secrets 템플릿 |
| `9b8d339` | feat: 콘텐츠 동시 비교 뷰로 UI 개편 | `render_yearly_comparison`, `render_monthly_comparison` 추가, main() 탭 → 비교 레이아웃 |
| `5361450` | feat: 콘텐츠 제목으로도 검색 가능한 드롭다운 추가 | `extract_all_contents`, 사이드바 3개 text_input → multiselect |

---

## 10. 다음 세션 시작 시 권장 첫 단계

1. **이 문서 먼저 읽기** (`docs/worklogs/` 에서 최신 날짜 워크로그)
2. `git log --oneline -20` 으로 이후 추가된 커밋 확인
3. 로컬 환경 복원 필요하면:
   ```bash
   cd /Users/linazzang/Projects/contentsefficiency
   .venv/bin/streamlit run app.py   # 로컬 테스트
   ```
4. 배포 앱이 살아있는지는 브라우저로 직접 확인 (curl은 303 나오는 정상 현상)
5. 이 문서의 **7.2 (미검증)** · **7.3-7.4 (확장 아이디어)** 리스트 검토하고 사용자에게 "다음으로 뭐 할지" 물어보기
