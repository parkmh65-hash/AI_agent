-- ====================================================================
-- 세종특별자치시 AI 문화유산 플랫폼 - Supabase Postgres + pgvector 마이그레이션 SQL
-- 실행 방법: Supabase Dashboard > SQL Editor에 복사하여 실행하세요.
-- ====================================================================

-- 1. pgvector 확장 모듈 활성화 (벡터 검색용)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. 사용자 (users) 테이블
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE,
    avatar_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. 문화유산 마스터 (heritages) 테이블
CREATE TABLE IF NOT EXISTS heritages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    h_id VARCHAR(50) UNIQUE NOT NULL, -- 예: H1~H119
    name VARCHAR(200) NOT NULL,
    address TEXT NOT NULL,
    description TEXT,
    era VARCHAR(100), -- 원본 비정규화 시대
    era_normalized VARCHAR(100) NOT NULL, -- 정규화 시대 (청동기시대/삼국시대/통일신라/고려/조선 전기/조선 중기/조선 후기/근대/현대)
    think_about TEXT, -- AI 생성 생각할거리
    image_url TEXT, -- 대표 이미지 URL
    dong_eup_myeon VARCHAR(100) NOT NULL, -- 읍면동 (연기면, 어진동, 전의면 등)
    category VARCHAR(100) DEFAULT '지정문화재', -- 유형문화재/보물/사찰유적 등
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    embedding VECTOR(768), -- Gemini / pgvector RAG 768차원 임베딩 벡터
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. 관련 뉴스 (heritage_news) 테이블
CREATE TABLE IF NOT EXISTS heritage_news (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    heritage_id UUID REFERENCES heritages(id) ON DELETE SET NULL,
    title VARCHAR(300) NOT NULL,
    link TEXT NOT NULL,
    published_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. 시민 추천 문화유산 (citizen_recommendations) 테이블 (담당자 승인 프로세스 포함)
CREATE TABLE IF NOT EXISTS citizen_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    photo_url TEXT,
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    address TEXT,
    reason TEXT NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT '신청중' CHECK (status IN ('신청중', '승인', '반려')),
    recommend_count INT DEFAULT 1,
    heart INT DEFAULT 0,
    feedback TEXT DEFAULT '담당자 현장 실사 및 확인 대기 중',
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reviewer_id UUID REFERENCES users(id) ON DELETE SET NULL,
    embedding VECTOR(768)
);

-- 6. 사용자 후기 (reviews) 테이블
CREATE TABLE IF NOT EXISTS reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    heritage_id UUID REFERENCES heritages(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    photo_url TEXT,
    rating INT DEFAULT 5 CHECK (rating BETWEEN 1 AND 5),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 7. 사용자 정의 여행 코스 (courses) 테이블
CREATE TABLE IF NOT EXISTS courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    transport_mode VARCHAR(50) DEFAULT '대중교통' CHECK (transport_mode IN ('대중교통', '자차', '도보')),
    total_time VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 8. 코스 - 문화유산 매핑 (course_items) 테이블
CREATE TABLE IF NOT EXISTS course_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    heritage_id UUID REFERENCES heritages(id) ON DELETE CASCADE,
    order_index INT NOT NULL,
    ai_content TEXT, -- 코스 생성 시 자동 작성된 잡지/동화/역사탐방 스토리
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ====================================================================
-- 인덱스 (Indexes) 및 pgvector HNSW 코사인 유사도 검색 인덱스
-- ====================================================================

CREATE INDEX IF NOT EXISTS idx_heritages_era ON heritages(era_normalized);
CREATE INDEX IF NOT EXISTS idx_heritages_dong ON heritages(dong_eup_myeon);
CREATE INDEX IF NOT EXISTS idx_citizen_status ON citizen_recommendations(status);

-- DROP FUNCTION IF EXISTS CASCADE to prevent PostgreSQL 42P13 return type conflict errors
DROP FUNCTION IF EXISTS match_heritages CASCADE;
DROP FUNCTION IF EXISTS match_heritages(vector, float, int) CASCADE;
DROP FUNCTION IF EXISTS match_heritages(vector, double precision, integer) CASCADE;
DROP FUNCTION IF EXISTS hybrid_search_heritages CASCADE;

-- pgvector RAG Cosine Distance Index (HNSW)
CREATE INDEX IF NOT EXISTS idx_heritages_embedding ON heritages 
USING hnsw (embedding vector_cosine_ops);

-- ====================================================================
-- RAG 벡터 시맨틱 코사인 유사도 검색 데이터베이스 함수 (RPC)
-- ====================================================================

CREATE OR REPLACE FUNCTION match_heritages (
  query_embedding VECTOR(1536),
  match_threshold FLOAT DEFAULT 0.2,
  match_count INT DEFAULT 5
)
RETURNS TABLE (
  id UUID,
  h_id VARCHAR,
  name VARCHAR,
  dong VARCHAR,
  description TEXT,
  era VARCHAR,
  thinking_point TEXT,
  similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    heritages.id,
    heritages.h_id,
    heritages.name,
    heritages.dong,
    heritages.description,
    heritages.era,
    heritages.thinking_point,
    1 - (heritages.embedding <=> query_embedding) AS similarity
  FROM heritages
  WHERE 1 - (heritages.embedding <=> query_embedding) > match_threshold
  ORDER BY heritages.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- ====================================================================
-- 초기 대표 시드 데이터 (Seed Initial Data)
-- ====================================================================

INSERT INTO heritages (h_id, name, address, description, era, era_normalized, think_about, image_url, dong_eup_myeon, category, lat, lng)
VALUES 
('H1', '세종 연기아문', '세종특별자치시 연기면 연기리 31-1', '조선시대 연기현의 관아 대문건물로 세종시 역사의 상징적 유적입니다.', '조선시대 초', '조선 전기', '조선시대 지방 관아의 입지와 옛 행정구역이 현재 행정도시 세종으로 변모해온 과정을 사유해봅시다.', 'https://images.unsplash.com/photo-1548013146-72479768bada?w=600&q=80', '연기면', '시도유형문화재', 36.5200, 127.2700),
('H2', '세종 비암사 극락보전', '세종특별자치시 전의면 다방리 512', '운주산 기슭 비암사에 위치한 극락보전으로 고풍스러운 단청과 아늑함이 특징입니다.', '조선전기', '조선 전기', '깊은 산속 비암사에서 세종시민들이 마음의 평온을 찾고 전통 문화를 체험하는 의미를 곱씹어봅시다.', 'https://images.unsplash.com/photo-1590523741831-ab7e8b8f9c7f?w=600&q=80', '전의면', '보물', 36.6300, 127.2000),
('H3', '초려 이유태 역사공원', '세종특별자치시 어진동 580', '조선 후기 저명한 유학자 초려 이유태 선생의 학문과 정신을 기념하기 위해 조성된 한옥 테마공원입니다.', '조선 후기', '조선 후기', '현대 신도시 아파트 단지 사이에 조화롭게 우뚝 선 한옥 공원이 주는 정서적 쉼터의 가치를 느껴봅시다.', 'https://images.unsplash.com/photo-1578632767115-351597cf2477?w=600&q=80', '어진동', '시도기념물', 36.5050, 127.2600),
('H4', '합강리 선사유적', '세종특별자치시 동면 합강리', '금강과 미호천이 합류하는 지점에 위치한 청동기시대 집터 및 선사 인류의 생활 터전입니다.', '청동기시대', '청동기시대', '두 강 줄기가 합쳐지는 비옥한 땅에서 선사 인류가 공동체를 형성했던 지혜를 상상해봅시다.', 'https://images.unsplash.com/photo-1509316975850-ff9c5deb0cd9?w=600&q=80', '연동면', '선사유적', 36.4900, 127.3200)
ON CONFLICT (h_id) DO NOTHING;
