-- ====================================================================
-- 세종특별자치시 AI 문화유산 스마트 플랫폼 - RAG Vector Store pgvector DDL
-- 실행 방법: Supabase Dashboard > SQL Editor에서 아래 쿼리를 실행해 주십시오.
-- ====================================================================

-- pgvector 확장 활성화
CREATE EXTENSION IF NOT EXISTS vector;

-- RAG 문서 청크를 저장하기 위한 heritage_documents 테이블 생성
CREATE TABLE IF NOT EXISTS heritage_documents (
  id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content   TEXT NOT NULL,
  metadata  JSONB NOT NULL DEFAULT '{}'::jsonb,
  embedding VECTOR(1536) -- OpenAI Embeddings (text-embedding-ada-002 또는 text-embedding-3-small) 규격
);

-- HNSW 인덱스 생성 (빠른 코사인 유사도 검색용)
CREATE INDEX IF NOT EXISTS idx_heritage_documents_embedding 
ON heritage_documents USING hnsw (embedding vector_cosine_ops);

-- 코사인 거리 기반 의미적 유사도 검색 함수 정의
CREATE OR REPLACE FUNCTION match_heritage_documents (
  query_embedding VECTOR(1536),
  match_threshold FLOAT,
  match_count INT
)
RETURNS TABLE (
  id UUID,
  content TEXT,
  metadata JSONB,
  similarity FLOAT
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    heritage_documents.id,
    heritage_documents.content,
    heritage_documents.metadata,
    1 - (heritage_documents.embedding <=> query_embedding) AS similarity
  FROM heritage_documents
  WHERE 1 - (heritage_documents.embedding <=> query_embedding) > match_threshold
  ORDER BY heritage_documents.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
