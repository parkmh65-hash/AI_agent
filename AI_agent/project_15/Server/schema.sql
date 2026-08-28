-- 1. Enable pgvector extension to work with embedding vectors
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create the fashion table (512 dimensions for CLIP ViT-B/32)
CREATE TABLE IF NOT EXISTS fashion (
  id bigserial PRIMARY KEY,
  image_name text,          -- Name of the image file (e.g. image_1.png)
  base64_data text,         -- Compressed Base64 string of the image
  embedding vector(512)     -- 512 dimensions for CLIP embeddings
);

-- 3. Create similarity search function for match_fashion RPC
CREATE OR REPLACE FUNCTION match_fashion (
  query_embedding vector(512),
  match_threshold float,
  match_count int
)
RETURNS TABLE (
  id bigint,
  image_name text,
  base64_data text,
  similarity float
)
LANGUAGE plpgsql STABLE
AS $$
BEGIN
  RETURN QUERY
  SELECT
    fashion.id,
    fashion.image_name,
    fashion.base64_data,
    1 - (fashion.embedding <=> query_embedding) AS similarity
  FROM fashion
  WHERE 1 - (fashion.embedding <=> query_embedding) > match_threshold
  ORDER BY fashion.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
