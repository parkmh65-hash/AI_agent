# 🏛️ 세종시 AI 문화유산 스마트 플랫폼 (Heritage Project ver_02)

세종시의 문화유산 탐방 경험을 혁신하는 **AI 기반 스마트 문화유산 플랫폼**입니다. 
시민 및 관광객을 위한 **모바일 앱(Citizen UI)**과 관리자를 위한 **통합 관제 시스템(Supervisor UI)**, 그리고 **FastAPI AI 에이전트 백엔드**로 구성되어 있습니다.

---

## 📐 시스템 아키텍처 (System Architecture)

```
[ Citizen App (GAS) ]      [ Supervisor Dashboard (GAS) ]
        │                               │
        ├───────────────────────────────┤
        ▼                               ▼
[ Supabase Client DB ]        [ Supabase Supervisor DB ]
  (문화유산/코스/후기)          (로그/AI 토큰/세션)
        │
        ▼
[ FastAPI Backend (Cloud Run) ]
  - RAG 검색 & AI 가이드북 생성 (OpenAI & Gemini)
  - Naver / Tour API 연동
```

---

## 📁 프로젝트 구조 (Directory Structure)

```
heritage/
├── .agents/                      # 에이전트 규칙 및 가이드
├── supabase_setup_guide.md       # Supabase DB 구축 & 환경변수 설정 상세 가이드
├── supabase_citizen_schema_update1.sql # Supabase citizen schema SQL
├── README.md                     # 프로젝트 설명서 (본 파일)
└── ver_02/
    ├── database_sync_migration.sql # ver_02 데이터베이스 동기화 마이그레이션 SQL
    ├── GAS/                      # 시민용 모바일 Web App (Google Apps Script)
    │   ├── appsscript.json       # Apps Script 매니페스트
    │   ├── Code.gs               # Apps Script 서버사이드 로직 (Supabase REST / FastAPI 연동)
    │   ├── Index.html            # 시민용 모바일 SPA 프론트엔드 (Tailwind/Lucide/JS)
    │   └── OAuth2.gs             # Google OAuth2 인증 모듈
    ├── GAS_supvisor/             # 관리자 통합 관제 Web App (Google Apps Script)
    │   ├── appsscript.json       # Apps Script 매니페스트
    │   ├── Code.gs               # 관제 서버사이드 로직 (실시간 로그/통계/시민 제보 관리)
    │   ├── Index.html            # 관제 텔레메트리 대시보드 프론트엔드
    │   └── OAuth2.gs             # 관리자 인증 모듈
    └── Server/                   # FastAPI 백엔드 (Google Cloud Run 배포용)
        ├── Dockerfile            # Containerize 설정
        ├── requirements.txt      # Python 의존성 패키지
        └── app/
            ├── config.py         # 환경변수 및 API 키 설정 (Pydantic Settings)
            ├── main.py           # FastAPI 라우트 & API 엔드포인트
            ├── insert_heritages.py # 초기 문화유산 데이터 배치 수집/입력 스크립트
            └── services/
                └── guidebook_service.py # AI 기반 시나리오/가이드북 생성 서비스
```

---

## ✨ 주요 기능 (Key Features)

### 1. 📱 시민용 모바일 서비스 (Citizen Web App)
- **맞춤형 탐방 코스 추천**: 이동 수단(도보/승용차 등) 및 일정에 맞는 동선 추천
- **AI 문화유산 스마트 가이드**: RAG(검색 증강 생성) 기반 AI 안내원 인터랙션
- **시민 추천 및 제보**: 숨은 문화유산 제보, 사진 업로드 및 승인 요청
- **후기 및 불편 신고**: 실시간 평점 작성 및 시설 개선 요청

### 2. 📊 관리자 통합 관제 (Supervisor Telemetry Dashboard)
- **실시간 데이터 모니터링**: 사용자 세션, 탐방 후기, 시민 제보 내역 실시간 확인
- **AI 토큰 & 비용 관리**: LLM(OpenAI/Gemini) 호출 토큰 사용량 및 레이턴시 추적
- **제보 승인/반려 관리**: 시민이 제출한 제보 검토 및 본 DB 승인 처리

### 3. 🚀 백엔드 & AI 엔진 (FastAPI Backend)
- **FastAPI / Python 3.11**: 비동기 API 엔드포인트 구축
- **OpenAI & Gemini API**: 가이드북 자동 생성 및 대화형 질의응답
- **공공 API 연동**: Naver Search & 한국관광공사 Tour API 연동

---

## 🛠️ 설치 및 배포 가이드 (Setup & Deployment)

### 1. Supabase DB 설정
`supabase_setup_guide.md` 파일을 참조하여 Supabase에서 Client DB와 Supervisor DB를 각각 구성하고 SQL 테이블을 생성합니다.

### 2. FastAPI 백엔드 배포 (Google Cloud Run)
```bash
cd ver_02/Server
docker build -t sejong-heritage-server .
# Google Cloud Artifact Registry 등록 및 Cloud Run 배포
```

### 3. Google Apps Script 연동
1. `ver_02/GAS` 및 `ver_02/GAS_supvisor` 코드를 각각의 Google Apps Script 프로젝트에 업로드합니다.
2. 스크립트 속성(Script Properties)에 `USER_SUPABASE_URL`, `USER_SUPABASE_KEY`, `SUPERVISOR_SUPABASE_URL`, `SUPERVISOR_SUPABASE_KEY`, `CLOUD_RUN_URL`을 지정합니다.
3. Web App으로 배포(Deploy as Web App)합니다.

---

## 📜 라이선스 (License)

본 프로젝트는 세종특별자치시 AI 문화유산 스마트 플랫폼 구축 사업의 일환으로 개발되었습니다.
