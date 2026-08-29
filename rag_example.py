import os
from dotenv import load_dotenv
from supabase import create_client
from langchain_community.document_loaders import YoutubeLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI

# Load environment variables from .env file
load_dotenv()

def run_rag_pipeline(youtube_url: str, user_question: str):
    """
    RAG (Retrieval-Augmented Generation) Pipeline:
    1. Loads YouTube video transcripts
    2. Chunks the text into smaller pieces
    3. Embeds and stores the chunks in Supabase (Postgres) Vector DB
    4. Performs semantic search to retrieve relevant context
    5. Feeds context + question to Gemini model to generate a precise answer
    """
    # 1. Credentials Check
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    
    if not supabase_url or not supabase_key or supabase_url == "your_supabase_url_here":
        print("[ERROR] Supabase credentials (SUPABASE_URL / SUPABASE_KEY) are not set in the .env file.")
        return
        
    if not gemini_api_key or gemini_api_key == "your_gemini_api_key_here":
        print("[ERROR] GEMINI_API_KEY is not configured in the .env file.")
        return

    # Initialize Supabase and Embedding model
    supabase = create_client(supabase_url, supabase_key)
    
    # Using Google's text-embedding-004 model (768 dimensions output)
    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
    
    # --- STEP 1: LOAD TRANSCRIPT ---
    print(f"\n[Step 1] Fetching transcripts from: {youtube_url}...")
    try:
        # Load transcript using LangChain's YouTube Loader (handles Korean & English)
        loader = YoutubeLoader.from_youtube_url(
            youtube_url, 
            add_video_info=False, 
            language=["ko", "en"]
        )
        docs = loader.load()
        video_title = docs[0].metadata.get("title", "Unknown Video")
        print(f"-> Loaded! Video Title: '{video_title}'")
    except Exception as e:
        print(f"[ERROR] Failed to load YouTube transcripts: {e}")
        return

    # --- STEP 2: CHUNK TEXT ---
    print("\n[Step 2] Splitting transcript text into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    chunks = text_splitter.split_documents(docs)
    print(f"-> Split into {len(chunks)} chunks.")

    # --- STEP 3: EMBED AND STORE IN SUPABASE ---
    print("\n[Step 3] Storing chunks & embeddings in Supabase vector store...")
    try:
        # SupabaseVectorStore automatically calls Gemini embeddings for each chunk and writes to DB
        vector_store = SupabaseVectorStore.from_documents(
            documents=chunks,
            embedding=embeddings,
            client=supabase,
            table_name="documents",
            query_name="match_documents"
        )
        print("-> Embedded and stored in Supabase successfully!")
    except Exception as e:
        print(f"[ERROR] Failed to store in Supabase database: {e}")
        print("💡 Hint: Ensure you have run the pgvector SQL script in Supabase dashboard to enable table 'documents' and function 'match_documents'.")
        return

    # --- STEP 4: RETRIEVE CONTEXT ---
    print(f"\n[Step 4] Querying Vector DB for: '{user_question}'...")
    retriever = vector_store.as_retriever(search_kwargs={"k": 3})
    retrieved_docs = retriever.invoke(user_question)
    
    print("-> Retrieved relevant chunks:")
    for idx, doc in enumerate(retrieved_docs):
        snippet = doc.page_content[:150].replace('\n', ' ')
        print(f"   [Chunk {idx+1}] {snippet}...")

    # --- STEP 5: GENERATE ANSWER WITH GEMINI ---
    print("\n[Step 5] Sending retrieved context to Gemini to answer...")
    context_text = "\n\n".join([doc.page_content for doc in retrieved_docs])
    
    prompt = f"""You are a helpful AI assistant. Use the following context from a YouTube video transcript to answer the question at the end.
If you do not know the answer based on the context, just say that you don't know (do not hallucinate).

Context:
{context_text}

Question: {user_question}
Answer (in Korean):"""

    # Initialize Gemini model
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash")
    response = llm.invoke(prompt)
    
    print("\n================== GEMINI ANSWER ==================")
    print(response.content)
    print("=====================================================")

if __name__ == "__main__":
    # Test execution configuration
    # Note: Replace with a public YouTube URL (with Korean/English transcripts) and your question.
    video_url = "https://www.youtube.com/watch?v=kCc8FmEb1nY"
    question = "영상에서 설명하는 주요 핵심 내용이 뭐야?"
    
    print("--- Starting YouTube RAG Pipeline Demonstration ---")
    run_rag_pipeline(video_url, question)
