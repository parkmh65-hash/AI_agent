# Google Apps Script (GAS) & Google Sites 클라이언트 배포 가이드

본 모듈은 **세종특별자치시 AI 문화유산 스마트 플랫폼**을 **Google Apps Script (GAS)** 환경에서 웹 애플리케이션으로 배포하고 **Google Sites**에 즉시 임베딩할 수 있도록 작성된 웹 클라이언트입니다.

---

## 📁 파일 구성 (`/gas`)

1. **`Code.gs`**: GAS 백엔드 서버 로직 (FastAPI Cloud Run URLFetchApp 통신 & Google Sheet 연동)
2. **`Index.html`**: 단일 페이지 웹 애플리케이션 (5대 메뉴 + 지도 + 통계 차트 + AI 스토리 + 관리자 모듈)
3. **`appsscript.json`**: GAS 런타임 및 웹앱 접근 권한 설정 파일

---

## 🚀 배포 절차 (Google Apps Script & Google Sites)

### 1단계: Google Apps Script 프로젝트 생성
1. [Google Apps Script](https://script.google.com/) 접속 후 **새 프로젝트**를 생성합니다.
2. 프로젝트 이름을 `세종시 AI 문화유산 스마트 플랫폼`으로 지정합니다.

### 2단계: 소스 코드 복사
1. `Code.gs` 파일 내용을 구글 앱스 스크립트의 `Code.gs`에 복사합니다.
2. 좌측 `+` 버튼을 클릭하여 **HTML 파일**을 추가하고 이름을 `Index`로 지정한 뒤, `Index.html` 내용을 복사합니다.
3. `Code.gs` 상단의 `FASTAPI_BACKEND_URL`을 Cloud Run 서버 주소로 업데이트합니다.

### 3단계: 웹 앱 배포 (Web App Deployment)
1. 우측 상단의 **배포 (Deploy)** -> **새 배포 (New deployment)** 클릭.
2. 유형 선택: **웹 앱 (Web App)**.
3. 설정:
   - **실행할 사용자 (Execute as)**: `나 (Me)`
   - **액세스 권한 (Who has access)**: `모든 사용자 (Anyone)`
4. **배포** 버튼 클릭 후 발행된 **웹 앱 URL**을 복사합니다.

### 4단계: Google Sites에 웹앱 임베딩 (Google Workspace 연동)
1. [Google Sites](https://sites.google.com/)에서 사이트 편집기를 엽니다.
2. 우측 메뉴의 **삽입 (Insert)** -> **URL로 임베딩 (Embed)** 선택.
3. 복사한 GAS 웹 앱 URL을 붙여넣고 페이지에 배치하면 신속 배포가 완성됩니다.
