-- =====================================================================
-- database_sync_migration.sql
-- 전국 스마트 문화유산 서비스 통합 데이터베이스 동기화 및 컬럼 정렬 마이그레이션 SQL
-- =====================================================================

-- 1. 지정 문화유산 테이블 (heritages) 생성 및 호환성 컬럼 정비
CREATE TABLE IF NOT EXISTS heritages (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    dong VARCHAR(100),
    address TEXT,
    description TEXT,
    image_url TEXT,
    like_count INT DEFAULT 0,
    lat NUMERIC(10, 8),
    lng NUMERIC(11, 8),
    thinking_point TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- heritages 테이블 위도/경도/좋아요 필드 호환성 보완
ALTER TABLE heritages ADD COLUMN IF NOT EXISTS latitude NUMERIC(10, 8);
ALTER TABLE heritages ADD COLUMN IF NOT EXISTS longitude NUMERIC(11, 8);
ALTER TABLE heritages ADD COLUMN IF NOT EXISTS heart INT DEFAULT 0;
ALTER TABLE heritages ADD COLUMN IF NOT EXISTS photo_url TEXT;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='heritages' AND column_name='lat') THEN
        UPDATE heritages SET latitude = COALESCE(latitude, lat);
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='heritages' AND column_name='lng') THEN
        UPDATE heritages SET longitude = COALESCE(longitude, lng);
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='heritages' AND column_name='like_count') THEN
        UPDATE heritages SET heart = COALESCE(heart, like_count);
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='heritages' AND column_name='image_url') THEN
        UPDATE heritages SET photo_url = COALESCE(photo_url, image_url);
    END IF;
END $$;


-- 2. 시민 제보 문화유산 테이블 (citizen_recommendations) 생성 및 필드 전면 동기화
CREATE TABLE IF NOT EXISTS citizen_recommendations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address VARCHAR(255),
    dong VARCHAR(100),
    lat NUMERIC(10, 8),
    lng NUMERIC(11, 8),
    description TEXT,
    image_url TEXT,
    status VARCHAR(50) DEFAULT '신청중',
    like_count INT DEFAULT 0,
    submitted_by VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- citizen_recommendations 필드 호환성 패치 (lat/latitude, lng/longitude, description/reason, user_id/submitted_by, photo_url/image_url)
ALTER TABLE citizen_recommendations ADD COLUMN IF NOT EXISTS latitude NUMERIC(10, 8);
ALTER TABLE citizen_recommendations ADD COLUMN IF NOT EXISTS longitude NUMERIC(11, 8);
ALTER TABLE citizen_recommendations ADD COLUMN IF NOT EXISTS reason TEXT;
ALTER TABLE citizen_recommendations ADD COLUMN IF NOT EXISTS user_id VARCHAR(100);
ALTER TABLE citizen_recommendations ADD COLUMN IF NOT EXISTS photo_url TEXT;
ALTER TABLE citizen_recommendations ADD COLUMN IF NOT EXISTS heart INT DEFAULT 0;
ALTER TABLE citizen_recommendations ADD COLUMN IF NOT EXISTS recommend_count INT DEFAULT 0;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='citizen_recommendations' AND column_name='lat') THEN
        UPDATE citizen_recommendations SET latitude = COALESCE(latitude, lat);
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='citizen_recommendations' AND column_name='lng') THEN
        UPDATE citizen_recommendations SET longitude = COALESCE(longitude, lng);
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='citizen_recommendations' AND column_name='description') THEN
        UPDATE citizen_recommendations SET reason = COALESCE(reason, description);
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='citizen_recommendations' AND column_name='image_url') THEN
        UPDATE citizen_recommendations SET photo_url = COALESCE(photo_url, image_url);
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='citizen_recommendations' AND column_name='like_count') THEN
        UPDATE citizen_recommendations SET heart = COALESCE(heart, like_count);
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='citizen_recommendations' AND column_name='submitted_by') THEN
        UPDATE citizen_recommendations SET user_id = COALESCE(user_id, submitted_by);
    END IF;
END $$;


-- 3. 당일 맞춤 코스 테이블 (courses) 생성 및 컬럼 보완
CREATE TABLE IF NOT EXISTS courses (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100),
    title VARCHAR(255) DEFAULT '전국 문화유산 코스',
    transport_mode VARCHAR(50) DEFAULT '승용차',
    total_duration_min INT DEFAULT 60,
    guidebook_result JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

ALTER TABLE courses ADD COLUMN IF NOT EXISTS guidebook_result JSONB;


-- 4. 코스 상세 매핑 테이블 (course_items) 생성 및 외래키 정렬
CREATE TABLE IF NOT EXISTS course_items (
    id SERIAL PRIMARY KEY,
    course_id INT REFERENCES courses(id) ON DELETE CASCADE,
    heritage_id VARCHAR(50) NOT NULL,
    sort_order INT NOT NULL
);


-- 5. 탐방 후기 및 피드백 테이블 (reviews) 생성
CREATE TABLE IF NOT EXISTS reviews (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100),
    heritage_name VARCHAR(255) NOT NULL,
    rating INT CHECK (rating BETWEEN 1 AND 5),
    review_text TEXT,
    is_improvement_needed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);


-- 6. [성능 고도화] RAG 검색 및 동적 매칭 쿼리 처리를 위한 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_heritages_dong ON heritages(dong);
CREATE INDEX IF NOT EXISTS idx_heritages_address ON heritages(address);
CREATE INDEX IF NOT EXISTS idx_citizen_recommendations_status ON citizen_recommendations(status);
CREATE INDEX IF NOT EXISTS idx_citizen_recommendations_address ON citizen_recommendations(address);
CREATE INDEX IF NOT EXISTS idx_course_items_course_id ON course_items(course_id);
CREATE INDEX IF NOT EXISTS idx_course_items_heritage_id ON course_items(heritage_id);
CREATE INDEX IF NOT EXISTS idx_reviews_user_id ON reviews(user_id);
CREATE INDEX IF NOT EXISTS idx_citizen_rec_status_name ON citizen_recommendations (status, name);

-- =====================================================================
-- 통합 동동화 쿼리 패치 완료
-- =====================================================================
