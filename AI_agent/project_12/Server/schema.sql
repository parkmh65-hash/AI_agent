-- 1. [IMPORTANT] If you have an existing 768-dimension documents table, run these DROP commands first:
-- DROP FUNCTION IF EXISTS match_documents(vector, float, int);
-- DROP FUNCTION IF EXISTS match_documents(vector, double precision, integer);
-- DROP TABLE IF EXISTS documents;

-- 2. Enable pgvector extension to work with embedding vectors
CREATE EXTENSION IF NOT EXISTS vector;

-- 3. Create the documents table (1536 dimensions)
CREATE TABLE IF NOT EXISTS documents (
  id bigserial PRIMARY KEY,
  content text,              -- Maps to LangChain's Document page_content
  metadata jsonb,            -- Maps to LangChain's Document metadata
  embedding vector(1536)     -- 1536 dimensions for OpenAI's text-embedding-3-small (default) / text-embedding-ada-002
);

-- 3. Create similarity search function for match_documents RPC
CREATE OR REPLACE FUNCTION match_documents (
  query_embedding vector(1536),
  match_threshold float,
  match_count int
)
RETURNS TABLE (
  id bigint,
  content text,
  metadata jsonb,
  similarity float
)
LANGUAGE plpgsql STABLE
AS $$
BEGIN
  RETURN QUERY
  SELECT
    documents.id,
    documents.content,
    documents.metadata,
    1 - (documents.embedding <=> query_embedding) AS similarity
  FROM documents
  WHERE 1 - (documents.embedding <=> query_embedding) > match_threshold
  ORDER BY documents.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
