-- alter_schema.sql
-- 데이터 구조 정렬 및 타입 호환성 무결성을 위한 스키마 변경 스크립트

-- 1. 기존 users 외래 키 제약 조건 안전 삭제
ALTER TABLE citizen_recommendations DROP CONSTRAINT IF EXISTS citizen_recommendations_user_id_fkey;
ALTER TABLE citizen_recommendations DROP CONSTRAINT IF EXISTS citizen_recommendations_reviewer_id_fkey;
ALTER TABLE courses DROP CONSTRAINT IF EXISTS courses_user_id_fkey;
ALTER TABLE reviews DROP CONSTRAINT IF EXISTS reviews_user_id_fkey;
ALTER TABLE heritage_likes DROP CONSTRAINT IF EXISTS heritage_likes_user_id_fkey;

-- 2. user_id 컬럼 타입을 VARCHAR(100)으로 변환 (기존 이메일/문자열 식별 지원)
ALTER TABLE citizen_recommendations ALTER COLUMN user_id TYPE VARCHAR(100);
ALTER TABLE citizen_recommendations ALTER COLUMN reviewer_id TYPE VARCHAR(100);
ALTER TABLE courses ALTER COLUMN user_id TYPE VARCHAR(100);
ALTER TABLE reviews ALTER COLUMN user_id TYPE VARCHAR(100);
ALTER TABLE heritage_likes ALTER COLUMN user_id TYPE VARCHAR(100);

-- 3. citizen_recommendations 테이블 컬럼명 정렬 (조건부 실행을 위한 PL/pgSQL 블록)
DO $$
BEGIN
  -- lat -> latitude 변경
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='citizen_recommendations' AND column_name='lat') THEN
    ALTER TABLE citizen_recommendations RENAME COLUMN lat TO latitude;
  END IF;

  -- lng -> longitude 변경
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='citizen_recommendations' AND column_name='lng') THEN
    ALTER TABLE citizen_recommendations RENAME COLUMN lng TO longitude;
  END IF;

  -- photo_url -> image_url 변경
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='citizen_recommendations' AND column_name='photo_url') THEN
    ALTER TABLE citizen_recommendations RENAME COLUMN photo_url TO image_url;
  END IF;

  -- reason -> description 변경
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='citizen_recommendations' AND column_name='reason') THEN
    ALTER TABLE citizen_recommendations RENAME COLUMN reason TO description;
  END IF;
END $$;
