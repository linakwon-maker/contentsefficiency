# 2026-04-27 · 콘텐츠별 요율 설정 · 추정 성능 개선 · UX 다듬기

> **작성 목적**: 다음 세션에서 이 프로젝트를 이어 작업할 때 빠르게 맥락을 복구할 수 있도록 오늘 한 변경(6커밋, app.py +318줄)의 **왜 / 무엇 / 어떻게** 와 다음 후보까지 정리. 코드는 git 에서 볼 수 있으니 **숨은 결정**과 **재발 방지** 중심.
>
> 이전 워크로그: `2026-04-23-mvp-launch.md` (MVP 구축·배포 + 같은 날 후속 4개 커밋). 이 문서는 그 후속.

---

## 0. TL;DR — 오늘 추가된 6개 커밋 한 줄 요약

| 해시 | 메시지 | 핵심 |
|------|--------|------|
| `e0e1ff0` | feat: 콘텐츠별 요율 설정 + 사이드바 추정 옵션 단순화 + 시트 로딩 최적화 | 단일 요율 → 콘텐츠별 dict, 사이드바 체크박스 제거, viewing_log 분리 캐시 |
| `0d3a582` | perf: 콘텐츠별 요율 변경 시 추정 매출 재계산 속도 대폭 개선 | 점유율과 요율 분리, factor 캐시. 슬라이더 변경 < 1초 |
| `a67848d` | fix: 결과 페이지 하위 섹션에서 일부 콘텐츠 제목 누락되던 문제 | df_out title 보강 + `_content_labels` safety net |
| `30f4170` | feat: 매출 추이 차트에 구간 셀렉터·range slider·스크롤 줌 추가 | Plotly rangeselector + rangeslider + scrollZoom |
| `aa00cab` | feat: 콘텐츠별 상세에 전체 총합계 표시 | yearly_summary 마지막 카드, pivot 마지막 행 |
| (이전) `b6dd7f9` → amend `e0e1ff0` | 동일 변경, author 정정 | committer 가 시스템 기본값으로 찍혀서 amend + force-push |

---

## 1. 컨텍스트 — 이 세션이 시작될 때 상태

### 1.1. 배경
사용자가 "저번 작업 이어서 할게" 로 시작 → 이전 세션 워크로그(`2026-04-23-mvp-launch.md`) 확인. 그 시점에서:
- MVP + FLAT 예상 + 정산금 미세팅 추정 기능까지 완성·배포된 상태 (1,035줄)
- 다음 후보: 11.4절에 6개 항목 정리됨

### 1.2. 환경 복원 시 주의
- **gh CLI 가 `/tmp/gh-bin` 에 없음** (이전 세션의 임시 설치, 리부트로 사라졌을 수 있음). 오늘 다시 깔았는데 지금은 다시 사라질 수 있는 위치임. 7.2 참조.
- **로컬 git config (repo-local) 가 비어 있었음**. 이전 세션에 `lina.kwon@watcha.com` 으로 설정했다고 워크로그에 적혀 있었지만 실제로는 안 들어가 있어 첫 커밋이 `니지 <linazzang@Lina.local>` 로 찍힘. 사용자 명시 승인으로 amend + force-push 로 정정. 이번 세션에 다시 repo-local 로 `Lina Kwon <lina.kwon@watcha.com>` 세팅함.
- **로컬 venv·streamlit 등은 그대로 살아있음** (`/Users/linazzang/Projects/contentsefficiency/.venv/`).

---

## 2. 사용자 요구 (시간 순)

이번 세션에 사용자가 제기한 요구는 다음과 같이 진화함:

1. **요율을 콘텐츠별로 따로 설정/변경해서 예상 매출을 보고 싶다** → `e0e1ff0`
2. **매출 종류 추출이 너무 오래 걸린다** → `e0e1ff0` 의 시트 로딩 최적화 (사이드바 단계)
3. **(반영 안 된 듯하다 — 배포해 달라)** → 커밋·푸시. Streamlit Cloud 자동 재배포.
4. **author 정보 정정** → 사용자 명시 승인으로 amend + force-push (`e0e1ff0`).
5. **결과 페이지 "엑셀 파일 분석" 자체가 너무 오래 걸린다** (요율 슬라이더 만질 때마다) → `0d3a582`. **이번 세션에서 가장 큰 단일 개선.**
6. **하위 섹션에서 일부 콘텐츠 제목이 코드만 보인다** → `a67848d`
7. **매출 추이 차트에 확대 기능** → `30f4170`
8. **콘텐츠별 상세에 총합계** → `aa00cab`

각 요구마다 즉시 구현·푸시 → Streamlit Cloud 자동 재배포 패턴이 자리 잡음.

---

## 3. 변경 1 — 콘텐츠별 요율 설정 (`e0e1ff0`)

### 3.1. 문제
이전 시점엔 **단일 `estimate_rate: float`** (사이드바 number_input 1개)만 존재. 사용자: "콘텐츠 별로 다른 요율인 경우도 있어서…"

### 3.2. 결정
- **사이드바의 "정산금 미세팅 콘텐츠 자동 추정" 체크박스 제거** → 추정은 **항상 작동**
- 사이드바 "3. 추정 매출 옵션" 은 **매출 종류 + 기본 요율** (신규 콘텐츠 초기값) 만 남김
- **결과 페이지 최상단**에 콘텐츠별 요율 number_input 3컬럼 (선택 콘텐츠 수만큼). 항상 표시.
- 위젯 키 `f"rate_{cid}"` 로 **콘텐츠별 값 영속화** — 다른 콘텐츠로 바꿔도 기존 값 유지
- **`st.session_state["query"]`** 에 조회 시점 스냅샷 저장. 요율 변경에 의한 rerun 에서도 같은 query 로 재계산됨.

### 3.3. 시그니처 변경
```python
load_sales_from_uploads(
    ...,
    estimate_rates: dict[str, float] | None = None,  # was: estimate_rate: float
    default_rate: float = 0.5,                       # 새로 추가
)
```
- `estimate_rates` 가 `None` 이면 빈 dict 로 처리.
- 추정 루프에서 `rate = estimate_rates.get(cid, default_rate)` 로 콘텐츠별 lookup.
- **추정치 배너**도 콘텐츠별 적용 요율 표시: `📺 제목 · 요율 0.50 · (2024)`

### 3.4. 사이드바·결과 페이지 흐름 (현재)
```
[사이드바]
  1. 엑셀 파일 업로드
  2. 매출 종류 필터 (Confidential 의 매출 종류)
  3. 추정 매출 옵션
     - 추정 매출 종류 (sales_log 의 매출 종류)
     - 기본 요율 (신규 콘텐츠 초기값)
  4. 콘텐츠 선택 (multiselect, 최대 3개)
  [조회 버튼]

[결과 페이지]
  ⚙️ 콘텐츠별 요율 설정  ← 항상 노출 (선택 콘텐츠 수만큼 number_input)
  ─ divider ─
  비교 콘텐츠 한 줄 요약
  추정치 배너 (콘텐츠별 요율 표시)
  📈 매출 추이 비교 (Plotly + range selector)
  💰 FLAT 예상 금액
  📋 연간 합계 비교
  📋 월별 상세 비교
  🔍 콘텐츠별 상세 (expander, 기본 닫힘)
```

### 3.5. 시트 로딩 최적화 (같은 커밋에 묶여 들어감)
**문제**: `_read_content_sheet(data)` 가 내부적으로 `_read_all_sheets(data)` 호출 → 매번 viewing_log(거대) 까지 같이 읽어서 사이드바 첫 로딩이 매우 느림.

**해결**: 시트 로딩을 시트 단위로 분리·캐시.
- `_get_sheet_names(data)` — 워크북 구조만 파싱. 시트명 목록만.
- `_read_confidential_sheet(data)` — Confidential 만 단독 로딩. `_read_content_sheet` 가 위임.
- `_read_log_sheet(data, keyword)` — `viewing_log` / `sales_log` 키워드 매칭으로 단일 시트만.
- `_read_all_sheets(data)` — 위 세 함수의 dict 래퍼 (호환 유지). **더 이상 한 번에 읽지 않음.**
- `extract_sales_log_types(file_datas)` 도 `_read_log_sheet(data, "sales_log")` 만 호출 → viewing_log 회피.

**결과**: 사이드바의 매출 종류·콘텐츠 목록 추출이 viewing_log 를 안 읽어 첫 로딩 시간이 크게 줄어듦. 나머지(estimate 시 viewing_log 필요)는 lazy 로드 + 캐시.

---

## 4. 변경 2 — 추정 매출 재계산 속도 개선 (`0d3a582`) ⭐ 가장 큰 단일 개선

### 4.1. 문제
사용자: "결과값 페이지에서 엑셀 파일 분석이 너무 오래 걸리네." (요율 슬라이더 한 번 움직일 때마다 5~30초씩 멈춤)

### 4.2. 진단
요율 변경 → rerun → `load_sales_from_uploads` 재실행 → 추정이 필요한 (cid, year) 마다 `compute_estimated_monthly` 호출 → **그 안에서 `viewing_log.groupby("month")["watch_minutes"].sum()` 등 거대 groupby 가 콘텐츠별로 매번 다시 실행**.

핵심 통찰:
- `viewing_log.groupby("month")["watch_minutes"].sum()` (분모) 는 **콘텐츠 무관 / 요율 무관** — 파일당 1번만 계산해서 모든 콘텐츠가 공유 가능.
- 콘텐츠별 시청분수도 **요율과 무관** — 콘텐츠당 1번만 계산하면 요율 슬라이더 움직여도 캐시 히트.
- 요율은 점유율 계산 결과에 **곱셈만** 하면 됨.

### 4.3. 해결 — 점유율과 요율 분리, 단계별 캐시
새로 만든 4개 헬퍼:

| 함수 | 캐시 단위 | 역할 |
|------|----------|------|
| `_viewing_log_total_by_month(data)` | 파일당 1회 | **분모** 캐시. 모든 콘텐츠가 공유 |
| `_sales_log_by_type_month(data, bill_type)` | 파일×매출종류 | 매출종류별 sales_log 합 |
| `_content_watch_minutes_by_month(data, content_id)` | 파일×콘텐츠 | 콘텐츠 시청분수 (최빈 category 기준) |
| `_estimated_factor_monthly(data, cid, bill_type, year)` | 위 3개 결합 — **요율 빼고** | **요율 변경 시 캐시 히트 → 곱셈만** |

`compute_estimated_monthly` 본문은 한 줄로 단순화:
```python
factor = _estimated_factor_monthly(data, content_id, bill_type, year)
return {m: (f * rate if pd.notna(f) else float("nan")) for m, f in factor.items()}
```

**시그니처도 변경**: `(viewing_log, sales_log, ...)` → `(data: bytes, ...)`. 이로써 `load_sales_from_uploads` 의 `sheets_by_year` 딕셔너리도 `{year: data_bytes}` 로 바뀜 (DataFrame 들고다니지 않음).

### 4.4. 캐시 히트율
- **첫 조회**: viewing_log groupby 한 번 실행 (이건 어쩔 수 없음)
- **요율 슬라이더 변경**: 모든 헬퍼 캐시 히트 → 곱셈만. 거의 즉시 (< 1초)
- **콘텐츠 추가**: 추가된 콘텐츠 시청분수만 새로 계산. 분모/매출 캐시 히트.
- **다른 매출 종류 선택**: `_sales_log_by_type_month` 만 새로. 분모/콘텐츠 캐시 히트.

---

## 5. 변경 3 — 콘텐츠 제목 매칭 누락 수정 (`a67848d`)

### 5.1. 문제
사용자: "콘텐츠별 요율 설정에서는 제목이 잘 들어가는데 매출 추이 비교, FLAT, 연간 합계, 월별 상세, 콘텐츠별 상세에서 어떤 콘텐츠는 코드 숫자만 보인다."

### 5.2. 원인 (두 가지가 겹침)
1. **추정 row 의 `content_title` 이 비어있을 수 있음** — Confidential 시트에 등장 안 한 콘텐츠 (예: viewing_log 에는 있지만 정산금 행 없는 경우)는 title 이 매칭 안 됨.
2. **`_content_labels` 가 첫 row 의 title 만 봄** — `sub["content_title"].iloc[0]`. 첫 row 가 추정 row(빈 title) 면 다른 row 에 title 있어도 무시.

상단 요율 설정은 **사이드바의 `extract_all_contents` 결과(매직시트의 모든 콘텐츠)를 fallback** 으로 가지고 있어서 멀쩡했고, 하위 섹션은 df 만 보고 있었음.

### 5.3. 해결 — 3단 보강
**단계 1**: `load_sales_from_uploads` **시작 시** `extract_all_contents(file_datas)` 결과로 `title_by_id` 미리 채움 → 어느 연도에 정산금 행이 없어도 다른 파일의 title 활용.

**단계 2**: `load_sales_from_uploads` **끝 부분**에서 `df_out` 의 빈/NaN `content_title` 을 `title_by_id` 매핑으로 일괄 채움. 추정 row 도 모두 제목 들어감.

**단계 3**: `_content_labels` 강화 — 빈 문자열 / `nan` 문자열 / NaN 을 건너뛰고 **비어있지 않은 첫 title** 채택:
```python
cleaned = sub["content_title"].dropna().astype(str).str.strip()
cleaned = cleaned[(cleaned != "") & (cleaned.str.lower() != "nan")]
if not cleaned.empty:
    title = cleaned.iloc[0]
```

**단계 4 (부수)**: `render_comparison_chart` 도 `_content_labels` 사용으로 통일하고 `groupby` key 에서 `content_title` 제거. **제목 변형으로 한 콘텐츠 라인이 둘로 쪼개지는 가능성**도 차단.

---

## 6. 변경 4 — 매출 추이 차트 확대 기능 (`30f4170`)

### 6.1. 추가된 것
| 기능 | 사용법 | 구현 |
|------|--------|------|
| 구간 셀렉터 버튼 | 차트 상단 좌측 `6개월` `1년` `2년` `3년` `전체` | `xaxis.rangeselector.buttons` |
| Range Slider | 차트 하단 미니 차트 양쪽 핸들 | `xaxis.rangeslider` |
| 마우스 휠 줌 | 차트 위 스크롤 | `config={"scrollZoom": True}` |
| 드래그 줌 | 마우스로 영역 선택 | `dragmode="zoom"` (Plotly 기본) |
| 줌 리셋 | 더블클릭 | Plotly 기본 |
| 보조 도구 | 라인/자유선/지우개 | `modeBarButtonsToAdd` |

레이아웃: 높이 520→560, 범례 위치 `y=-0.45` (rangeslider 자리 확보), 셀렉터 `bgcolor="#f5f5f5"`.

### 6.2. 주의할 부분
- `xaxis.type="date"` 명시 — Plotly 가 자동 추론하긴 하지만 rangeselector 가 작동하려면 명확한 게 안전.
- `rangeslider.thickness=0.06` — 너무 두꺼우면 본 차트 영역을 잠식.

---

## 7. 변경 5 — 총합계 표시 (`aa00cab`)

`render_yearly_summary`: 연도 카드 끝에 **🏁 전체 합계** 카드 추가 (`grand_total = yearly["total"].sum()`, 부가 표시는 전체 월 평균 `df["revenue"].mean()`).

`render_pivot`: 마지막 행 **"총합"** 추가:
- 1~12월 컬럼: 그 월의 모든 연도 합 (`pivot.iloc[:, :12].sum(axis=0)`)
- 연간 합계 컬럼: 전체 합 (`pivot["연간 합계"].sum()`)
- 연간 평균 컬럼: 전체 셀 평균 (`pivot.iloc[:, :12].stack().mean()`)

---

## 8. 코드 구조 (현재 `app.py`, 1,200줄)

이전 워크로그의 6절·11.5절에서 다음이 더 추가/변경됨:

```
app.py
├── (L1-50)    설정·상수 (FLAT_DEPRECIATION, FLAT_YEAR_MULTIPLIERS 그대로)
├── (L52-80)   require_password()
├── (L83-170) 유틸 (_normalize / _find_column / _extract_month / _to_number / ...)
├── (L171-215) _to_month_timestamp (월 값 유연 파싱)
├── (L217-280) ★ 시트 로딩 (커밋 e0e1ff0 으로 분리됨)
│   ├── _get_sheet_names(data)              ← 신규
│   ├── _read_confidential_sheet(data)      ← 신규 (Confidential 단독)
│   ├── _read_log_sheet(data, keyword)      ← 신규 (viewing/sales 단독)
│   ├── _read_all_sheets(data)              ← dict 래퍼로 단순화
│   └── _read_content_sheet(data)           ← _read_confidential_sheet 위임
├── (L282-380) ★ 추정 (커밋 0d3a582 으로 분리됨)
│   ├── _viewing_log_total_by_month(data)            ← 신규 (분모, 캐시)
│   ├── _sales_log_by_type_month(data, bill_type)    ← 신규 (캐시)
│   ├── _content_watch_minutes_by_month(data, cid)   ← 신규 (캐시)
│   ├── _estimated_factor_monthly(data, cid, bill_type, year)  ← 신규 (요율 빼고 캐시)
│   └── compute_estimated_monthly(data, cid, bill_type, rate, year)  ← factor × rate
├── (L383-405) extract_sales_log_types (sales_log 단독 로딩으로 변경)
├── (L408-465) extract_all_contents / _format_content_option / extract_sales_categories
├── (L468-660) load_sales_from_uploads
│   ├── 시그니처: estimate_rates: dict + default_rate
│   ├── ★ 함수 시작 시 extract_all_contents 로 title_by_id 보강 (커밋 a67848d)
│   ├── sheets_by_year[year] = data_bytes (DataFrame 안 들고감)
│   ├── 추정: rate = estimate_rates.get(cid, default_rate)
│   └── ★ df_out 끝부분에서 빈 content_title 을 title_by_id 로 일괄 채움
├── (L663-720) ★ 렌더 (총합계 추가)
│   ├── render_pivot ← 마지막 행 "총합"
│   ├── render_yearly_summary ← 끝에 "🏁 전체 합계" 카드
├── (L723-740) _content_labels ← 빈/nan title 무시, 비어있지 않은 첫 title 채택
├── (L743-840) compute_flat_estimates / render_flat_estimates / render_yearly_comparison / render_monthly_comparison
├── (L843-930) render_comparison_chart ← rangeselector + rangeslider + scrollZoom, _content_labels 사용
└── (L933-1200) main()
    ├── 사이드바: 1.업로드 / 2.매출종류 필터 / 3.추정 매출 옵션 (체크박스 제거) / 4.콘텐츠 선택
    ├── ★ session_state["query"] 스냅샷 저장 (조회 후에도 rerun 시 재사용)
    ├── ★ 결과 최상단: ⚙️ 콘텐츠별 요율 설정 (number_input 3컬럼, 항상 표시)
    └── 결과: 비교 콘텐츠 요약 → 추정치 배너(콘텐츠별 요율) → 추이 → FLAT → 연간 → 월별 → 콘텐츠별 상세
```

### 중요한 코드 규약 (이전 워크로그 6절에서 보강)
- 모든 시트 로딩은 **분리 캐시**. 새 시트 종류 추가 시 `_read_log_sheet(data, "<keyword>")` 패턴 따를 것.
- 추정 계산은 **요율을 분리**. 새 추정 변형 만들 때도 `_estimated_factor_*` 형태로 요율과 분리해 두면 슬라이더 UX 가 빠름.
- `_content_labels` 는 **df 의 어떤 row 가 빈 title 이어도 안전**해야 함. 새 렌더 함수 만들 때 직접 `df["content_title"].iloc[0]` 쓰지 말고 항상 `_content_labels` 경유.
- 위젯 키 `rate_{cid}` 는 콘텐츠별 영속화에 필수. 이 명명 규칙 유지.

---

## 9. 배포·인증·git 운영 메모

### 9.1. 인증 상태
- gh CLI 를 `/tmp/gh-bin` 에 v2.91.0 재설치함. `~/.config/gh/hosts.yml` 에 토큰 살아있어 `gh auth status` 즉시 OK.
- `~/.gitconfig` 의 credential helper 가 `/tmp/gh-bin auth git-credential` 로 설정되어 있음 — gh 가 사라지면 push 시 즉시 실패.
- repo-local `user.email = lina.kwon@watcha.com`, `user.name = Lina Kwon` 이번 세션에서 다시 세팅.

### 9.2. force push 사례
- 첫 커밋 `b6dd7f9` 가 `니지 <linazzang@Lina.local>` (시스템 기본) 으로 author 찍혀서 사용자 명시 승인 후 `git commit --amend --reset-author --no-edit` + `git push --force-with-lease`. 결과 → `e0e1ff0`.
- 다음에도 author 가 시스템 기본으로 찍혔다면 같은 절차로 정정. **단, 명시 승인 받기 전엔 절대 force-push 하지 말 것.**

### 9.3. 배포 흐름
- `git push origin main` → Streamlit Cloud webhook 자동 재배포 (1~3분).
- Streamlit Cloud Secrets 는 여전히 웹 UI 전용 (CLI 불가). `.streamlit/secrets.toml` 은 gitignore 됨.

---

## 10. 사용자 스타일 추가 관찰 (이전 워크로그 11.6절 보강)

- **"배포해" 같은 간결 지시**가 곧 명시 승인. force-push 같은 위험 작업도 사용자가 "응 고쳐줘" 같은 짧은 답을 주면 진행 가능 (단, 의도가 명확할 때만).
- **반응형 / 짧은 응답을 선호**. 길게 설명할 필요 없을 땐 표·핵심만.
- **"왜 이게 필요해?" 보다 "이렇게 해줘" 패턴**. 의도 추측해 구현 → 결과 확인 → 다음 요청.
- 수정 후 즉시 배포까지 가는 흐름이 자연스러움. 매 커밋마다 commit 직후 push 가 사실상 표준.
- 시각적 명확성을 중요시: "코드 숫자만 보인다" 같은 문제는 데이터 정확성 못지 않게 즉각적 우선순위.

---

## 11. 디버깅·재발 방지 메모 (이전 워크로그 11.7절 보강)

- **요율 슬라이더가 다시 느려지면**: `_estimated_factor_monthly` 캐시가 깨졌는지 확인. 새 인자가 추가되면 캐시 키가 바뀌어 매번 미스 됨. `data: bytes` 외에 `dict` 같은 unhashable 인자가 들어가지 않도록.
- **사이드바 첫 로딩이 다시 느려지면**: `_read_content_sheet` 가 `_read_all_sheets` 를 다시 호출하지 않는지 확인. (이전엔 그랬다가 viewing_log 까지 끌어와서 느렸음.)
- **차트에서 한 콘텐츠가 두 라인으로 보이면**: `render_comparison_chart` 의 `groupby` 키에 `content_title` 이 다시 들어갔는지 확인. 제목이 row 마다 다르게 들어가면 쪼개짐. (현재는 `content_id` 만 키.)
- **콘텐츠 라벨이 코드만 보이면**: `_content_labels` 가 빈 title 처리하는지 + `load_sales_from_uploads` 가 `extract_all_contents` 로 보강하는지 확인.
- **rangeslider 가 본 차트 영역을 잠식하면**: `rangeslider.thickness` 줄이거나 fig height 늘리기.
- **요율 위젯 값이 콘텐츠 바꿔도 그대로면**: 위젯 key 가 `rate_{cid}` 로 cid 별로 분리되었는지 확인. 같은 key 쓰면 위젯이 공유됨.

---

## 12. 다음 세션을 위한 후보 (이전 워크로그 11.4절 갱신)

이전 워크로그 11.4 후보 중 **남아있는 것**:

- [ ] **2020~2024 파일 실제 테스트** — 여전히 미검증. 2025 외 파일 업로드 시 `_to_month_timestamp` 가 새 월 표기 변형(예: `'2024.10. 01'`) 처리 OK 인지 확인. 문제 시 `_to_month_timestamp` 의 정규식부터.
- [ ] **추정치 시각 구분** — 라인 차트에서 추정 구간을 점선, 표에서 추정 셀을 이탤릭/음영. 현재는 배너 안내만 있음. `is_estimate` 컬럼은 이미 df 에 있음.
- [ ] **FLAT 예상 금액에 추정치 포함 표시** — 지금은 추정·실제 섞여 계산되는데 표에 구분 없음.
- [ ] **bill_name ↔ type 매핑 테이블** — 있으면 추정 정확도 ↑.
- [ ] **추정 요율 자동 추천** — 같은 콘텐츠의 다른 매출종류 요율, 유사 콘텐츠의 평균 요율을 초기값으로 제안.
- [ ] **viewing_log 기반 시청분수 트렌드 별도 뷰**.

이번 세션에 새로 떠오른 후보:

- [ ] **요율 일괄 적용 버튼** — "선택 콘텐츠 모두에 0.5 적용" 같은 빠른 reset. 현재 콘텐츠가 많아질수록 반복 입력이 부담.
- [ ] **요율 프리셋 저장** — 자주 쓰는 요율 조합을 저장/복원 (예: "B-1 전체 0.5", "C-2 전체 0.7"). `st.session_state` 로 가능, 영속화는 `.streamlit/` 또는 별도 export.
- [ ] **결과 엑셀 다운로드 버튼** — 피벗·비교표·FLAT 표를 그대로 xlsx 로 export. (이전 워크로그 7.4 에도 있던 항목)
- [ ] **콘텐츠 비교 4개+ 지원** — 현재 max_selections=3. 사용자 패턴 보고 필요 시 늘리거나 행렬형 비교 뷰.
- [ ] **차트의 "급락 임계값(-30%)" 사이드바 노출** — 이전 워크로그 7.4 에서 언급. 1줄 number_input 으로 가능.
- [ ] **요율 변경 후 처음 결과를 본 직후의 안내** — 사용자가 슬라이더를 조작해야 한다는 것을 즉시 깨닫게. 현재는 상단 캡션만 있음.

---

## 13. 다음 세션 시작 시 권장 첫 단계

1. **이 문서 + 이전 워크로그(`2026-04-23-mvp-launch.md`) 두 개 모두 읽기**.
2. `git log --oneline -20` 로 새 커밋 확인.
3. 로컬 환경 복원 필요 시:
   ```bash
   cd /Users/linazzang/Projects/contentsefficiency
   .venv/bin/streamlit run app.py
   ```
4. 배포 앱 (https://watcha-content-efficiency.streamlit.app) 살아있는지 브라우저로 직접 확인. (curl 은 303 — 정상)
5. **gh CLI** 가 `/tmp/gh-bin` 에 살아있는지 `ls /tmp/gh-bin`. 없으면 9.1 절 따라 재설치 (토큰은 keychain 에 보존).
6. **repo-local git config** 확인: `git config --get user.email` → `lina.kwon@watcha.com` 인지.
7. 사용자에게 12절 후보 검토 요청 — 보통 사용자는 자기 우선순위가 있음.

---

## 14. 부록 — 이번 세션의 사용자 메시지 흐름 (요약)

- "저번 작업 이어서 할게" → 이전 워크로그 읽고 후보 정리
- "콘텐츠 요율을 각 콘텐츠마다 설정, 변경해서 예상 매출을 볼 수 있게" → 1차 구현 (체크박스 게이트 있는 채로)
- "매출 종류 추출이 되게 오래 걸리네" → 시트 로딩 분리·캐시
- "콘텐츠 별로 다른 요율인 경우도 있어서 결과값 페이지에서 각 콘텐츠별 요율을 조정해서 결과값을 볼 수 있게 해줘" → 체크박스 게이트 제거, 항상 표시
- "수정한 거 맞아? 아직 반영 안된 거 같은" → commit·push 안 됐다는 안내
- "배포해" → push 진행 (gh 재설치 필요했음)
- "응 고쳐줘" → author 정보 amend + force-push
- "결과값 페이지에서 엑셀 파일 분석이 너무 오래걸리네" → 점유율과 요율 분리, factor 캐시 (가장 큰 win)
- "콘텐츠별 상세에서 어떤 콘텐츠는 타이틀 명이 매치가 안되고" → title 보강 + `_content_labels` safety net
- "매출 추이 비교는 원하는 구간을 더 자세히 볼 수 있게 확대 기능" → rangeselector + rangeslider + scrollZoom
- "콘텐츠별 상세에서 총합계도 보고 싶어" → yearly_summary 카드 + pivot 행 추가
- "지금까지 작업한거 다음에 작업할 때 context 확보하기 위해서 최대한 자세하게 log를 작성" → 본 문서

각 요청마다 **추가 컨텍스트 질문 없이 즉시 구현·푸시**가 표준 패턴이었음.
