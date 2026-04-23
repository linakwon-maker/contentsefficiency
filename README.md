# 왓챠 콘텐츠 매출 분석 도구 (MVP)

연도별 매출 **엑셀 파일**을 업로드하고 콘텐츠 ID 1~3개를 입력하면 2020~2026년 월별 매출을 피벗 테이블·추이 차트로 한 눈에 보여주는 내부용 Streamlit 앱.

## 특징
- 구글 시트/서비스 계정/사내 권한 요청 **전부 불필요** — 엑셀 파일 업로드만으로 동작
- 업로드된 데이터는 **세션 메모리에만** 존재. 앱이 데이터를 영구 저장하지 않음
- 비밀번호 게이트로 팀 외부 접근 차단
- 컬럼명 **자동 감지** (`콘텐츠 ID` / `content_id` / `1월` / `Jan` 등)
- 전월 대비 30% 이상 매출 급락 지점 자동 강조

## 로컬 실행

```bash
# 1. 가상환경 만들고 의존성 설치
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. 비밀번호 설정
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# → secrets.toml 을 열어 app_password 값 입력

# 3. 실행
.venv/bin/streamlit run app.py
```

브라우저에서 http://localhost:8501 열기 → 비밀번호 입력 → 엑셀 파일 업로드 → 콘텐츠 ID 입력 → 조회.

## 엑셀 파일 요구사항

- **파일명에 연도(4자리) 포함**: `2020.xlsx`, `sales_2023.xlsx`, `콘텐츠매출_2024.xlsx` 등 모두 OK
- **각 파일 안에 최소 다음 컬럼 존재**:
  - 콘텐츠 ID (이름은 `content_id`, `콘텐츠 ID`, `id` 등 자동 감지)
  - 1~12월 매출 (`1월`~`12월` 또는 `Jan`~`Dec` 또는 `1`~`12` 자동 감지)
  - (선택) 콘텐츠 제목 컬럼
- 컬럼명이 위 후보와 다르면 `.streamlit/secrets.toml` 의 `[columns]` 블록으로 수동 매핑

## 배포 (Streamlit Community Cloud)

1. 이 저장소를 **비공개 GitHub repo** 에 push (`.streamlit/secrets.toml` 은 gitignore 걸려있음)
2. https://share.streamlit.io → New app → main 브랜치 / `app.py` 선택
3. Advanced settings → **Secrets** 탭에 `app_password` 등록
4. Deploy → 배포 URL + 비밀번호 팀원에게 공유
5. **매출 엑셀 파일은 코드에 포함되지 않고, 접속한 사용자가 매번 업로드**하는 구조

## 보안 모델

- 매출 데이터는 앱 서버 메모리(세션)에만 존재 → 세션 종료 시 사라짐
- 코드 저장소, Streamlit Secrets, GitHub 어디에도 매출 데이터가 올라가지 않음
- 접근 통제: **앱 비밀번호** + **엑셀 파일을 가진 사용자**의 이중 조건
