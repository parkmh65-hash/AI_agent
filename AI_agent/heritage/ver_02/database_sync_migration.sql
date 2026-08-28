-- database_sync_migration.sql - ver_02 Database Setup

-- 1. Create official heritages table if not exists
CREATE TABLE IF NOT EXISTS public.heritages (
    id SERIAL PRIMARY KEY,
    h_id VARCHAR(50) UNIQUE,
    name VARCHAR(255) NOT NULL,
    address VARCHAR(255),
    dong_eup_myeon VARCHAR(100),
    category VARCHAR(100),
    era_normalized VARCHAR(100),
    latitude NUMERIC(10, 6),
    longitude NUMERIC(10, 6),
    description TEXT,
    parking_yn CHAR(1) DEFAULT 'Y',
    restroom_yn CHAR(1) DEFAULT 'Y',
    image_url TEXT,
    like_count INT DEFAULT 50,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 2. Create citizen recommendations table if not exists
CREATE TABLE IF NOT EXISTS public.citizen_recommendations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address VARCHAR(255),
    description TEXT,
    latitude NUMERIC(10, 6),
    longitude NUMERIC(10, 6),
    image_url TEXT,
    user_id VARCHAR(255) DEFAULT 'user@sejong.go.kr',
    status VARCHAR(50) DEFAULT '대기',
    recommend_count INT DEFAULT 1,
    heart INT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. Create saved courses table if not exists
CREATE TABLE IF NOT EXISTS public.courses (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) DEFAULT 'guest@sejong.go.kr',
    course_name VARCHAR(255) NOT NULL,
    description TEXT,
    transport VARCHAR(50) DEFAULT '승용차',
    total_duration INT DEFAULT 0,
    items JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 4. Safe PL/pgSQL block to dynamically ensure correct lat/lng properties exist
DO $$
BEGIN
    -- Check if latitude is missing in heritages
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
          AND table_name = 'heritages' 
          AND column_name = 'latitude'
    ) THEN
        ALTER TABLE public.heritages ADD COLUMN latitude NUMERIC(10,6);
    END IF;

    -- Check if longitude is missing in heritages
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
          AND table_name = 'heritages' 
          AND column_name = 'longitude'
    ) THEN
        ALTER TABLE public.heritages ADD COLUMN longitude NUMERIC(10,6);
    END IF;

    -- Check if latitude is missing in citizen_recommendations
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
          AND table_name = 'citizen_recommendations' 
          AND column_name = 'latitude'
    ) THEN
        ALTER TABLE public.citizen_recommendations ADD COLUMN latitude NUMERIC(10,6);
    END IF;

    -- Check if longitude is missing in citizen_recommendations
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
          AND table_name = 'citizen_recommendations' 
          AND column_name = 'longitude'
    ) THEN
        ALTER TABLE public.citizen_recommendations ADD COLUMN longitude NUMERIC(10,6);
    -- Check if user_id is missing in courses
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
          AND table_name = 'courses' 
          AND column_name = 'user_id'
    ) THEN
        ALTER TABLE public.courses ADD COLUMN user_id VARCHAR(255) DEFAULT 'guest@sejong.go.kr';
    END IF;
END $$;

-- 5. Build indexes for geographical coordinate queries and user courses
CREATE INDEX IF NOT EXISTS idx_heritages_coords ON public.heritages(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_citizen_coords ON public.citizen_recommendations(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_courses_user ON public.courses(user_id);

-- 6. Enable pgvector extension and create courses_vector table
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.courses_vector (
    id SERIAL PRIMARY KEY,
    course_name VARCHAR(255) NOT NULL,
    description TEXT,
    transport VARCHAR(50) DEFAULT '승용차',
    total_duration INT DEFAULT 0,
    items JSONB DEFAULT '[]'::jsonb,
    embedding vector(1536), -- OpenAI embedding dimensions
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 7. Create RPC function for pgvector similarity match search
CREATE OR REPLACE FUNCTION match_courses (
  query_embedding vector(1536),
  match_threshold float,
  match_count int
)
RETURNS TABLE (
  id int,
  course_name varchar,
  description text,
  transport varchar,
  total_duration int,
  items jsonb,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    courses_vector.id,
    courses_vector.course_name,
    courses_vector.description,
    courses_vector.transport,
    courses_vector.total_duration,
    courses_vector.items,
    1 - (courses_vector.embedding <=> query_embedding) AS similarity
  FROM courses_vector
  WHERE 1 - (courses_vector.embedding <=> query_embedding) > match_threshold
  ORDER BY courses_vector.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- 8. Create users profile table for authentication session cache
CREATE TABLE IF NOT EXISTS public.users_profile (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    nickname VARCHAR(100),
    auth_provider VARCHAR(50) DEFAULT 'google',
    last_login TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);
