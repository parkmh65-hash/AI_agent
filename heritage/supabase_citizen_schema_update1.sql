-- supabase_citizen_schema_update.sql
-- 시민 제보 문화유산(citizen_recommendations) 테이블 컬럼 매핑 보완 및 호환성 강화 SQL

-- 1. 위도/경도 호환성 컬럼 추가 (lat/latitude, lng/longitude 대응)
ALTER TABLE citizen_recommendations ADD COLUMN IF NOT EXISTS latitude NUMERIC(10, 8);
ALTER TABLE citizen_recommendations ADD COLUMN IF NOT EXISTS longitude NUMERIC(11, 8);

-- 2. 설명/사유 호환성 컬럼 추가 (description/reason 대응)
ALTER TABLE citizen_recommendations ADD COLUMN IF NOT EXISTS reason TEXT;

-- 3. 유저 식별자 및 사진 주소 호환성 컬럼 추가 (user_id/submitted_by, photo_url/image_url 대응)
ALTER TABLE citizen_recommendations ADD COLUMN IF NOT EXISTS user_id VARCHAR(100);
ALTER TABLE citizen_recommendations ADD COLUMN IF NOT EXISTS photo_url TEXT;

-- 4. 하트 및 추천 카운트 호환성 컬럼 추가 (heart/like_count, recommend_count 대응)
ALTER TABLE citizen_recommendations ADD COLUMN IF NOT EXISTS heart INT DEFAULT 0;
ALTER TABLE citizen_recommendations ADD COLUMN IF NOT EXISTS recommend_count INT DEFAULT 0;

-- 기존 레코드가 있을 경우 호환성 컬럼들 값 동기화 (존재하는 컬럼만 동적 갱신)
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

-- 6. 승인 데이터 빠른 조회를 위한 복합 인덱스 보완
CREATE INDEX IF NOT EXISTS idx_citizen_rec_status_name 
ON citizen_recommendations (status, name);
