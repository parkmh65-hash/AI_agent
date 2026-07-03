import os
import sys
import glob
from dotenv import load_dotenv
from pypdf import PdfReader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore
from supabase import create_client

# Load environment variables (handling case where .env is in parent directories)
current_file_dir = os.path.dirname(os.path.abspath(__file__))
parent_dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(current_file_dir))), ".env")
if os.path.exists(parent_dotenv_path):
    load_dotenv(dotenv_path=parent_dotenv_path)
else:
    load_dotenv()

PDF_DIR = r"C:\Users\user\Downloads\pdf"
TABLE_NAME = "documents"
QUERY_NAME = "match_documents"

def ingest_pdfs():
    print("=== Start PDF Ingestion Pipeline (Project 05) ===")
    
    # 1. Check environment variables
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not supabase_url or supabase_url == "your_supabase_url_here":
        print("[ERROR] SUPABASE_URL is not configured.")
        return
    if not supabase_key or supabase_key == "your_supabase_anon_key_here":
        print("[ERROR] SUPABASE_KEY is not configured.")
        return
    if not openai_key or openai_key == "your_openai_api_key_here":
        print("[ERROR] OPENAI_API_KEY is not configured.")
        return

    # Initialize Supabase client
    supabase = create_client(supabase_url, supabase_key)
    
    # 2. Check if table 'documents' exists
    try:
        supabase.table(TABLE_NAME).select("id").limit(1).execute()
        print("[OK] 'documents' table exists in Supabase. Proceeding with ingestion...")
    except Exception as e:
        print("\n[ERROR] 'documents' table does not exist or is not accessible in Supabase.")
        print(f"Error detail: {e}")
        print("\nPlease run the following SQL commands in your Supabase SQL Editor to initialize the database:")
        
        schema_path = os.path.join(current_file_dir, "schema.sql")
        if os.path.exists(schema_path):
            with open(schema_path, "r", encoding="utf-8") as f:
                print("\n" + "=" * 40 + "\n" + f.read() + "\n" + "=" * 40 + "\n")
        else:
            print("\nError: schema.sql file not found.")
            
        print("After running the SQL commands, please run this ingestion script again.")
        sys.exit(1)

    # 3. Find all PDFs in local directory
    if not os.path.exists(PDF_DIR):
        print(f"[ERROR] Directory does not exist: {PDF_DIR}")
        return
        
    pdf_files = glob.glob(os.path.join(PDF_DIR, "*.pdf"))
    if not pdf_files:
        print(f"[ERROR] No PDF files found in {PDF_DIR}")
        return
        
    print(f"Found {len(pdf_files)} PDF files to process:")
    for f in pdf_files:
        print(f" - {os.path.basename(f)}")
    
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small", dimensions=768)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    all_chunks = []
    
    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        print(f"\nProcessing: {filename}...")
        try:
            reader = PdfReader(pdf_path)
            num_pages = len(reader.pages)
            print(f"-> Total pages: {num_pages}")
            
            for page_idx, page in enumerate(reader.pages):
                text = page.extract_text()
                if not text or not text.strip():
                    continue
                
                # Split text on page level to keep chunk page metadata accurate
                chunks = text_splitter.split_text(text)
                for chunk_idx, chunk in enumerate(chunks):
                    doc = Document(
                        page_content=chunk,
                        metadata={
                            "source": filename,
                            "page": page_idx + 1,
                            "chunk_id": f"{filename}_p{page_idx+1}_c{chunk_idx}"
                        }
                    )
                    all_chunks.append(doc)
            print(f"-> Successfully extracted and chunked {filename}.")
        except Exception as e:
            print(f"[ERROR] Failed to process {filename}: {e}")
            
    if not all_chunks:
        print("No text chunks extracted from PDF files.")
        return
        
    print(f"\nTotal extracted chunks: {len(all_chunks)}")
    print("Uploading embeddings and document chunks to Supabase pgvector...")
    
    try:
        # Initialize Vector Store
        vector_store = SupabaseVectorStore(
            client=supabase,
            embedding=embeddings,
            table_name=TABLE_NAME,
            query_name=QUERY_NAME
        )
        
        # Batch uploading to avoid network limits or rate limits
        batch_size = 50
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i + batch_size]
            vector_store.add_documents(batch)
            print(f"-> Uploaded batch {i // batch_size + 1} ({len(batch)} chunks)")
            
        print("\n=== PDF Ingestion Succeeded! ===")
    except Exception as e:
        print(f"\n[ERROR] Failed to upload to Supabase: {e}")

if __name__ == "__main__":
    ingest_pdfs()
