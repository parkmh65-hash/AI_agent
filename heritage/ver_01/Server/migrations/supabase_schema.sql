-- ====================================================================
-- 세종특별자치시 AI 문화유산 스마트 플랫폼 - Supabase PostgreSQL DDL Script
-- 실행 방법: Supabase Dashboard > SQL Editor에서 아래 쿼리를 붙여넣고 [Run] 버튼을 클릭하세요.
-- ====================================================================

-- 1. 확장 모듈 활성화 (UUID 및 암호화)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. 사용자 (users) 테이블
CREATE TABLE IF NOT EXISTS users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email         VARCHAR(255) UNIQUE NOT NULL,
  name          VARCHAR(100),
  password_hash TEXT,
  role          VARCHAR(20) NOT NULL DEFAULT 'citizen', -- citizen | admin
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- 3. 문화유산 (heritages) 마스터 통합 테이블
CREATE TABLE IF NOT EXISTS heritages (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  h_id              VARCHAR(50),
  name              VARCHAR(200) NOT NULL,
  era               VARCHAR(100),
  dong              VARCHAR(50),
  latitude          DOUBLE PRECISION,
  longitude         DOUBLE PRECISION,
  description       TEXT,
  thinking_point    TEXT,
  source            VARCHAR(20) NOT NULL DEFAULT 'registered', -- registered(국가/지자체) | citizen(시민제보)
  status            VARCHAR(20) NOT NULL DEFAULT 'pending',    -- pending(대기) | approved(승인) | rejected(반려)
  needs_improvement BOOLEAN DEFAULT false,                     -- 개선 필요 문화유산 여부
  like_count        INT DEFAULT 0,
  naver_map_url     TEXT,
  google_map_url    TEXT,
  reported_by       UUID REFERENCES users(id) ON DELETE SET NULL,
  report_reason     TEXT,
  reviewer_note     TEXT,
  created_at        TIMESTAMPTZ DEFAULT now(),
  updated_at        TIMESTAMPTZ DEFAULT now()
);

-- 기존 테이블이 구버전으로 존재하는 경우 모든 필수 신규 컬럼 자동 추가 (안전성 보장)
ALTER TABLE heritages ADD COLUMN IF NOT EXISTS h_id VARCHAR(50);
ALTER TABLE heritages ADD COLUMN IF NOT EXISTS dong VARCHAR(50);
ALTER TABLE heritages ADD COLUMN IF NOT EXISTS era VARCHAR(100);
ALTER TABLE heritages ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;
ALTER TABLE heritages ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;
ALTER TABLE heritages ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE heritages ADD COLUMN IF NOT EXISTS thinking_point TEXT;
ALTER TABLE heritages ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT 'registered';
ALTER TABLE heritages ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'pending';
ALTER TABLE heritages ADD COLUMN IF NOT EXISTS needs_improvement BOOLEAN DEFAULT false;
ALTER TABLE heritages ADD COLUMN IF NOT EXISTS like_count INT DEFAULT 0;
ALTER TABLE heritages ADD COLUMN IF NOT EXISTS naver_map_url TEXT;
ALTER TABLE heritages ADD COLUMN IF NOT EXISTS google_map_url TEXT;
ALTER TABLE heritages ADD COLUMN IF NOT EXISTS reported_by UUID REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE heritages ADD COLUMN IF NOT EXISTS report_reason TEXT;
ALTER TABLE heritages ADD COLUMN IF NOT EXISTS reviewer_note TEXT;
ALTER TABLE heritages ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

-- citizen_recommendations 테이블 heart(좋아요) 컬럼 자동 추가
ALTER TABLE citizen_recommendations ADD COLUMN IF NOT EXISTS heart INT DEFAULT 0;

-- 이전 버전 컬럼(dong_eup_myeon, lat, lng, think_about)이 존재하는 경우 값 자동 이관
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='heritages' AND column_name='dong_eup_myeon') THEN
    UPDATE heritages SET dong = dong_eup_myeon WHERE dong IS NULL;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='heritages' AND column_name='lat') THEN
    UPDATE heritages SET latitude = lat WHERE latitude IS NULL;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='heritages' AND column_name='lng') THEN
    UPDATE heritages SET longitude = lng WHERE longitude IS NULL;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='heritages' AND column_name='think_about') THEN
    UPDATE heritages SET thinking_point = think_about WHERE thinking_point IS NULL;
  END IF;
END $$;



-- 4. 문화유산 이미지 (heritage_images) 테이블 (Supabase Storage URL 매핑)
CREATE TABLE IF NOT EXISTS heritage_images (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  heritage_id UUID REFERENCES heritages(id) ON DELETE CASCADE,
  image_url   TEXT NOT NULL,
  sort_order  INT DEFAULT 0
);

-- 5. 문화유산 좋아요 (heritage_likes) 중복 방지 매핑 테이블
CREATE TABLE IF NOT EXISTS heritage_likes (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  heritage_id UUID REFERENCES heritages(id) ON DELETE CASCADE,
  user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
  created_at  TIMESTAMPTZ DEFAULT now(),
  CONSTRAINT  unique_heritage_user_like UNIQUE (heritage_id, user_id)
);

-- 6. 코스 (courses) 테이블
CREATE TABLE IF NOT EXISTS courses (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            UUID REFERENCES users(id) ON DELETE SET NULL,
  title              VARCHAR(200),
  transport_mode     VARCHAR(50),
  total_duration_min INT,
  is_public          BOOLEAN DEFAULT false, -- 시민 추천 코스 공공 노출 여부
  created_at         TIMESTAMPTZ DEFAULT now()
);

-- 7. 코스 구성 항목 (course_items) 테이블
CREATE TABLE IF NOT EXISTS course_items (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id   UUID REFERENCES courses(id) ON DELETE CASCADE,
  heritage_id UUID REFERENCES heritages(id) ON DELETE CASCADE,
  sort_order  INT NOT NULL
);

-- 8. 탐방 후기 (reviews) 테이블
CREATE TABLE IF NOT EXISTS reviews (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            UUID REFERENCES users(id) ON DELETE SET NULL,
  course_id          UUID REFERENCES courses(id) ON DELETE SET NULL,
  heritage_id        UUID REFERENCES heritages(id) ON DELETE SET NULL,
  rating             SMALLINT CHECK (rating BETWEEN 1 AND 5),
  companion_type     VARCHAR(50),
  content            TEXT,
  is_recommended     BOOLEAN DEFAULT false,
  is_public          BOOLEAN DEFAULT true,
  parking_available  BOOLEAN,
  parking_note       TEXT,
  restroom_available BOOLEAN,
  restroom_note      TEXT,
  nearby_restaurant  BOOLEAN,
  created_at         TIMESTAMPTZ DEFAULT now()
);

-- 9. 후기 첨부 사진 (review_images) 테이블
CREATE TABLE IF NOT EXISTS review_images (
  id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  review_id UUID REFERENCES reviews(id) ON DELETE CASCADE,
  image_url TEXT NOT NULL
);

-- 10. AI 여행잡지 생성 이력 (travel_magazines) 테이블
CREATE TABLE IF NOT EXISTS travel_magazines (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id     UUID REFERENCES courses(id) ON DELETE CASCADE,
  content_html  TEXT,
  pdf_url       TEXT,
  sent_to_email VARCHAR(255),
  sent_at       TIMESTAMPTZ,
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- ====================================================================
-- 색인 (Indexes) 생성 - 고성능 검색 및 정렬용
-- ====================================================================
CREATE INDEX IF NOT EXISTS idx_heritages_source_status ON heritages(source, status);
CREATE INDEX IF NOT EXISTS idx_heritages_dong ON heritages(dong);
CREATE INDEX IF NOT EXISTS idx_heritages_era ON heritages(era);
CREATE INDEX IF NOT EXISTS idx_reviews_heritage ON reviews(heritage_id);

-- ====================================================================
-- 초기 관리자 및 대표 시드 데이터 삽입
-- ====================================================================
INSERT INTO users (email, name, password_hash, role)
VALUES ('admin@sejong.go.kr', '세종시 관리자', '$2b$10$X87K.dM51kYwS5F8QyOce.1J5E1s2s1Z1', 'admin')
ON CONFLICT (email) DO NOTHING;

INSERT INTO heritages (name, era, dong, latitude, longitude, description, thinking_point, source, status, like_count)
VALUES 
('세종 비암사 (극락보전)', '통일신라/고려', '전의면', 36.6488, 127.1895, '삼국시대 계유명전씨아미타불비상이 발견된 세종의 천년고찰입니다.', '백제와 신라 유민들이 비암사에서 불상을 조성하며 빌었던 염원은 무엇이었을까요?', 'registered', 'approved', 42),
('전의 초수 (왕의 물)', '조선시대 (세종)', '전의면', 36.6812, 127.1998, '조선 세종대왕의 안질을 치료하기 위해 길어 올린 약수가 나오던 역사의 현장입니다.', '세종대왕의 안질을 고친 전의 초수의 효험과 애민정신을 느껴보세요.', 'registered', 'approved', 38),
('임난수 장군 숭모각 및 은행나무', '고려/조선 초', '세종동', 36.4950, 127.2710, '고려말 절신 임난수 장군이 지켜낸 600년 넘는 천연기념물 은행나무입니다.', '조선 창업의 바람 속에서도 지켜낸 한 선비의 충절을 생각해보세요.', 'registered', 'approved', 29)
ON CONFLICT DO NOTHING;
