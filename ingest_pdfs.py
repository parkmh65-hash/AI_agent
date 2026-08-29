import os
import glob
from dotenv import load_dotenv
from pypdf import PdfReader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore
from supabase import create_client

# Load environment variables
load_dotenv()

PDF_DIR = r"C:\Users\user\Downloads\pdf"
TABLE_NAME = "documents"
QUERY_NAME = "match_documents"

def ingest_pdfs():
    print("=== Start PDF Ingestion Pipeline ===")
    
    # 1. Check environment variables
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or supabase_url == "your_supabase_url_here":
        print("[ERROR] SUPABASE_URL is not configured.")
        return
    if not supabase_key or supabase_key == "your_supabase_anon_key_here":
        print("[ERROR] SUPABASE_KEY is not configured.")
        return
    # Find all PDFs
    pdf_files = glob.glob(os.path.join(PDF_DIR, "*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {PDF_DIR}")
        return
        
    print(f"Found {len(pdf_files)} PDF files to process.")
    
    # Initialize Supabase and Embedding model
    supabase = create_client(supabase_url, supabase_key)
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
        # Save to vector store
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
