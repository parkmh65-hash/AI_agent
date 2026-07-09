import os
import sys
import glob
import time
from dotenv import load_dotenv
from pypdf import PdfReader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore
from supabase import create_client

# Load environment variables from standard location
dotenv_path = r"C:\Anti-project\.env"
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    load_dotenv()

PDF_DIR = r"C:\Users\user\Downloads\pdf"
TABLE_NAME = "documents"
QUERY_NAME = "match_documents"

def get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if not supabase_url or supabase_url == "your_supabase_url_here":
        raise ValueError("SUPABASE_URL is not set.")
    if not supabase_key or supabase_key == "your_supabase_anon_key_here":
        raise ValueError("SUPABASE_KEY is not set.")
    return create_client(supabase_url, supabase_key)

def verify_table_exists(supabase):
    try:
        supabase.table(TABLE_NAME).select("id").limit(1).execute()
        return True
    except Exception as e:
        print(f"[Warning] Supabase table '{TABLE_NAME}' check failed: {e}")
        return False

def show_sql_instructions():
    print("\n" + "="*80)
    print(" [REQUIRED SQL SCHEMA] 'documents' table does not exist or is inaccessible.")
    print(" Please execute the following SQL in your Supabase SQL Editor:")
    print("="*80)
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
    if os.path.exists(schema_path):
        with open(schema_path, "r", encoding="utf-8") as f:
            print(f.read())
    else:
        print("""
-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Create documents table
CREATE TABLE IF NOT EXISTS documents (
  id bigserial PRIMARY KEY,
  content text,
  metadata jsonb,
  embedding vector(1536)
);

-- Create match_documents similarity search function
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
        """)
    print("="*80 + "\n")

def ingest_local_pdfs():
    print("=== Starting PDF Ingestion Pipeline (1536 Dimensions) ===")
    
    # Check keys
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        print("[ERROR] OPENAI_API_KEY environment variable is missing.")
        sys.exit(1)
        
    try:
        supabase = get_supabase_client()
    except Exception as e:
        print(f"[ERROR] Supabase client initialization failed: {e}")
        sys.exit(1)
        
    if not verify_table_exists(supabase):
        show_sql_instructions()
        sys.exit(1)
        
    # Check directory
    if not os.path.exists(PDF_DIR):
        print(f"[ERROR] PDF directory does not exist: {PDF_DIR}")
        sys.exit(1)
        
    pdf_files = glob.glob(os.path.join(PDF_DIR, "*.pdf"))
    if not pdf_files:
        print(f"[ERROR] No PDF files found in {PDF_DIR}")
        sys.exit(1)
        
    print(f"Found {len(pdf_files)} PDF files to process.")
    for f in pdf_files:
        print(f" - {os.path.basename(f)}")
        
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small") # Defaults to 1536 dimensions
    
    # Splitters for Parent-Child Document Retrieval
    parent_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
    child_splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=50)
    
    all_child_documents = []
    
    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        print(f"\nProcessing PDF: {filename}")
        try:
            reader = PdfReader(pdf_path)
            num_pages = len(reader.pages)
            print(f"-> Pages: {num_pages}")
            
            for page_idx, page in enumerate(reader.pages):
                text = page.extract_text()
                if not text or not text.strip():
                    continue
                
                # 1. Split page into Parent chunks
                parent_chunks = parent_splitter.split_text(text)
                for p_idx, parent_chunk in enumerate(parent_chunks):
                    # 2. Split each Parent chunk into Child chunks
                    child_chunks = child_splitter.split_text(parent_chunk)
                    for c_idx, child_chunk in enumerate(child_chunks):
                        doc = Document(
                            page_content=child_chunk,
                            metadata={
                                "source": filename,
                                "page": page_idx + 1,
                                "parent_content": parent_chunk,
                                "chunk_id": f"{filename}_p{page_idx+1}_parent{p_idx}_child{c_idx}"
                            }
                        )
                        all_child_documents.append(doc)
            print(f"-> Finished extraction for: {filename}")
        except Exception as e:
            print(f"[ERROR] Failed to process {filename}: {e}")
            
    if not all_child_documents:
        print("No document chunks extracted. Exiting.")
        return
        
    print(f"\nTotal child chunks created: {len(all_child_documents)}")
    print("Uploading embedded child chunks to Supabase...")
    
    try:
        vector_store = SupabaseVectorStore(
            client=supabase,
            embedding=embeddings,
            table_name=TABLE_NAME,
            query_name=QUERY_NAME
        )
        
        # Ingest in batches to avoid rate limits
        batch_size = 50
        for i in range(0, len(all_child_documents), batch_size):
            batch = all_child_documents[i:i + batch_size]
            vector_store.add_documents(batch)
            print(f"-> Ingested batch {i // batch_size + 1} ({len(batch)} chunks)")
            
        print("\n=== Ingestion Completed Successfully ===")
    except Exception as e:
        print(f"\n[ERROR] Failed to upload to Supabase: {e}")

if __name__ == "__main__":
    ingest_pdfs_start = time.time()
    ingest_local_pdfs()
    print(f"Ingestion process took {time.time() - ingest_pdfs_start:.2f} seconds.")
