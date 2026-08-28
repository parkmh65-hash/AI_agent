# Supabase 구축 및 설정 가이드 (Client & Supervisor)

이 가이드는 사용자를 위한 **모바일 서비스 DB**와 관리자를 위한 **통합 관제 Telemetry DB**를 Supabase 상에 격리 구축하고, Google Apps Script(GAS) 백엔드에 안전하게 속성을 연동하는 절차를 설명합니다.

---

## ⚙️ 1단계: Supabase 프로젝트 생성 및 인증 설정

사용자용(`USER`)과 관리자용(`SUPERVISOR`)으로 각각 **두 개의 Supabase 독립 프로젝트**를 생성하는 것을 권장합니다.

1. **Supabase Dashboard** (https://supabase.com)에 로그인합니다.
2. **New Project**를 생성합니다:
   * **Project 1 (사용자 모바일 앱용)**: 예) `sejong-heritage-client`
   * **Project 2 (관리자 통합 관제용)**: 예) `sejong-heritage-supervisor`
3. 각 프로젝트의 `Project Settings` ➔ `API` 메뉴로 이동하여 다음의 값을 안전한 곳에 복사해 둡니다:
   * **Project URL**
   * **anon public API key**
4. **Google SSO 인증 활성화 (인증 관리)**:
   * Supabase Dashboard ➔ `Authentication` ➔ `Providers` 로 이동합니다.
   * `Google`을 활성화(Enabled)하고 Client ID와 Client Secret을 연동합니다.

---

## 🛠️ 2단계: Google Apps Script(GAS) 환경 변수 설정

GAS 백엔드 프록시가 각각 분리된 DB 저장소와 통신하도록 **프로젝트 속성(Script Properties)**을 지정합니다.

1. Google Apps Script 에디터 화면으로 이동합니다.
2. 좌측 메뉴의 **톱니바퀴 아이콘 (프로젝트 설정)**을 클릭합니다.
3. 스크롤을 내려 **스크립트 속성 (Script Properties)** 섹션을 찾습니다.
4. **스크립트 속성 편집**을 클릭하고 다음 4개의 키-값 쌍을 기입합니다:

| 스크립트 속성 키 (Key) | 설명 (Description) | 예시 값 (Value Example) |
| :--- | :--- | :--- |
| `USER_SUPABASE_URL` | 사용자용 Supabase API 주소 | `https://wylcqlmffchvufxpxydc.supabase.co` |
| `USER_SUPABASE_KEY` | 사용자용 Supabase anon public API 키 | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` |
| `SUPERVISOR_SUPABASE_URL` | 관리자용 Supabase API 주소 | `https://your-supervisor-db.supabase.co` |
| `SUPERVISOR_SUPABASE_KEY` | 관리자용 Supabase anon public API 키 | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` |
| `CLOUD_RUN_URL` | RAG 및 AI 가이드북 FastAPI 서버 주소 | `https://heritage-538192513096.us-central1.run.app` |

---

## 💾 3단계: 사용자용 데이터베이스 테이블 구성 SQL (Client DB)

**사용자용 Supabase 프로젝트(Project 1)**의 SQL Editor에서 다음 SQL문을 실행하여 테이블 및 인덱스를 생성합니다:

```sql
-- 1. 문화유산 본체 테이블 (heritages)
CREATE TABLE IF NOT EXISTS heritages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    h_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    address TEXT NOT NULL,
    dong VARCHAR(100),
    era VARCHAR(100),
    era_normalized VARCHAR(100),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    description TEXT,
    thinking_point TEXT,
    source VARCHAR(50) DEFAULT 'registered',
    status VARCHAR(50) DEFAULT 'approved',
    like_count INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. 문화유산 이미지 테이블 (heritage_images)
CREATE TABLE IF NOT EXISTS heritage_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    heritage_id UUID REFERENCES heritages(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. 코스 마스터 테이블 (courses)
CREATE TABLE IF NOT EXISTS courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    title VARCHAR(255) NOT NULL,
    transport_mode VARCHAR(50) DEFAULT '승용차',
    total_duration_min INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. 코스 상세 아이템 매핑 테이블 (course_items)
CREATE TABLE IF NOT EXISTS course_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    heritage_id VARCHAR(50) NOT NULL,
    sort_order INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. 탐방 후기 및 불편 신고 피드백 테이블 (reviews)
CREATE TABLE IF NOT EXISTS reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    heritage_name VARCHAR(255) NOT NULL,
    rating INT CHECK (rating >= 1 AND rating <= 5),
    text TEXT,
    is_improvement_needed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. 시민 제보 추천 테이블 (citizen_recommendations)
CREATE TABLE IF NOT EXISTS citizen_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    address TEXT NOT NULL,
    reason TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    photo_url TEXT,
    status VARCHAR(50) DEFAULT '대기', -- '대기', '승인', '반려'
    heart INT DEFAULT 1,
    recommend_count INT DEFAULT 1,
    submitted_by VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ====================================================
-- [가속 최적화] 주요 조회용 외래키 및 상태 조건 복합 인덱스
-- ====================================================
CREATE INDEX IF NOT EXISTS idx_heritages_dong ON heritages(dong);
CREATE INDEX IF NOT EXISTS idx_citizen_status ON citizen_recommendations(status);
CREATE INDEX IF NOT EXISTS idx_reviews_user_id ON reviews(user_id);
CREATE INDEX IF NOT EXISTS idx_course_items_course ON course_items(course_id);
```

---

## 📊 4단계: 관리자용 데이터베이스 테이블 구성 SQL (Supervisor DB)

**관리자용 Supabase 프로젝트(Project 2)**의 SQL Editor에서 다음 SQL문을 실행하여 모니터링 로그 보관을 가동합니다:

```sql
-- 1. 사용자 로그인 세션 로그 테이블 (user_sessions)
CREATE TABLE IF NOT EXISTS user_sessions (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    login_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    user_agent TEXT
);

-- 2. AI 에이전트 서비스 사용 정보 로그 테이블 (ai_usage_logs)
CREATE TABLE IF NOT EXISTS ai_usage_logs (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(255) NOT NULL,
    api_type VARCHAR(100) NOT NULL, -- 'RAG_Query', 'Guidebook_Generation'
    prompt_tokens INT DEFAULT 0,
    completion_tokens INT DEFAULT 0,
    latency_ms INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- ====================================================
-- [가속 최적화] 모니터링 수집/정렬 쿼리용 내림차순 가속 인덱스
-- ====================================================
CREATE INDEX IF NOT EXISTS idx_user_sessions_email ON user_sessions(email);
CREATE INDEX IF NOT EXISTS idx_user_sessions_login_at ON user_sessions(login_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_usage_logs_type_date ON ai_usage_logs(api_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_usage_logs_user ON ai_usage_logs(user_email);
```
