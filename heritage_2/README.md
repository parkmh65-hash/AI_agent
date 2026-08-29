# 스마트 문화유산 & 탐방 통합 플랫폼 (Smart Cultural Heritage Platform)

대한민국 국가유산 및 세종특별자치시 문화유산 데이터를 활용하여 구축한 모바일 반응형 **스마트 문화유산 및 여행 탐방 통합 플랫폼**입니다. Single Page Application (SPA) 프론트엔드, FastAPI 백엔드, Google Apps Script (GAS) 호환 구조로 설계되었습니다.

---

## 🌟 주요 기능 및 특징

1. **정직한 데이터 & 무결성 (Honest Data Integrity)**
   - 이미지 URL이 없거나 깨진 경우 가짜 이미지를 절대 임의 표출하지 않으며, **"📷 이미지 없음"** 전용 태그를 명확하게 표시합니다.
2. **iframe & 보안 제약 안전 인증 (Glassmorphic Auth System)**
   - iframe 환경에서 `prompt()`를 절대 사용하지 않으며, `localStorage` 차단 시 메모리 세션 폴백을 제공합니다.
   - Google, Kakao, Naver 및 이메일 로그인과 게스트 폴백 모드를 지원합니다.
3. **PGRST204 Auto-Pruning Engine (FastAPI 백엔드)**
   - Supabase PostgREST 테이블 컬럼 불일치(PGRST204) 발생 시, 오류 메시지에서 미존재 컬럼을 자동으로 추론하여 페이로드에서 제거한 후 최대 3회 재시도합니다.
4. **Leaflet & Leaflet.AntPath 대화형 지도**
   - 세종시 중심 좌표(`[36.50, 127.26]`) 기반 대화형 지도를 렌더링하고, **Haversine 공식 기반 Nearest-Neighbor 알고리즘(TSP)**으로 최단 경로 마커 정렬 및 애니메이션 경로 라인을 표출합니다.
5. **3단계 스마트 탐방 워크플로우**
   - **1단계**: RAG 기반 AI 맞춤 코스 탐색 (상위 5개 유산 선정 및 TSP 동선)
   - **2단계**: 내 맞춤 코스 담기/삭제 및 Supabase `courses` 테이블 보관
   - **3단계**: Web Speech API (`window.speechSynthesis`) 오디오 가이드북 음성 TTS 낭독 (재생, 일시정지, 속도 조절)
6. **시민 제보 (Citizen Recommendations)**
   - 주소 입력 시 OpenStreetMap Nominatim 지오코딩 자동 수행 및 `description` ↔ `reason`, `image_url` ↔ `photo_url`, `user_id` ↔ `submitted_by` 이중 필드 보정 저장을 지원합니다.

---

## 📁 프로젝트 구조

```
heritage_2/
├── index.html        # Glassmorphic SPA 프론트엔드 (HTML5, Vanilla CSS, JS, Leaflet.js)
├── main.py           # Python FastAPI 백엔드 (RAG, TSP, Nominatim, PGRST204 Auto-Prune, Supabase)
├── Code.gs           # Google Apps Script (GAS) HTML Service 및 API Proxy 스크립트
├── requirements.txt  # FastAPI dependencies
└── README.md         # 프로젝트 가이드
```

---

## 🚀 실행 가이드

### 1. Python 백엔드 실행
```bash
# 패키지 설치
pip install -r requirements.txt

# FastAPI 서버 실행 (포트 8000)
uvicorn main:app --reload --port 8000
```
- API 문서 Swagger UI: `http://localhost:8000/docs`

### 2. 환경 변수 설정 (`.env` 선택 사항)
백엔드 API 키 미설정 시에도 내장 로컬 데이터셋 및 휴리스틱 에이전트로 완전하게 동작합니다.
```env
SUPABASE_URL=https://your-supabase-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
OPENAI_API_KEY=sk-your-openai-api-key
```

### 3. 프론트엔드 접속
- `index.html` 파일을 웹 브라우저에서 직접 열거나 로컬 웹 서버로 접속할 수 있습니다.

### 4. Google Apps Script (GAS) 배포
- Google Drive에서 새 Google Apps Script 생성 후 `Code.gs`와 `index.html` 내용 작성.
- `웹 앱으로 배포(Deploy as Web App)` 선택 후 실행 권한을 `나(Me)`, 접속 대상을 `모든 사용자(Anyone)`로 지정하여 배포.
