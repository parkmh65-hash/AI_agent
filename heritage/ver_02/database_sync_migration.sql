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
    END IF;
END $$;

-- 5. Build indexes for geographical coordinate queries
CREATE INDEX IF NOT EXISTS idx_heritages_coords ON public.heritages(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_citizen_coords ON public.citizen_recommendations(latitude, longitude);
