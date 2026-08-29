import os
from langchain_core.tools import tool
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

@tool
def retrieve(query: str) -> list:
    """검색 쿼리를 바탕으로 벡터 데이터베이스(Supabase)에서 관련 정보를 검색합니다.

    Args:
        query: 검색할 쿼리 문자열
    """
    # Handle direct invocation with args dict
    if isinstance(query, dict):
        query_str = query.get("query", "")
    else:
        query_str = query

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if (not supabase_url or not supabase_key or 
        supabase_url == "your_supabase_url_here" or 
        supabase_key == "your_supabase_anon_key_here"):
        print("[WARNING] Supabase credentials are missing. Returning fallback mock results.")
        return [
            Document(
                page_content=f"'{query_str}'에 대한 가상 검색 결과: Supabase 설정이 필요합니다. RAG 시스템 구축을 위해 .env 파일에 올바른 SUPABASE_URL과 SUPABASE_KEY를 입력해주세요.",
                metadata={"source": "mock"}
            )
        ]

    try:
        supabase = create_client(supabase_url, supabase_key)
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small", dimensions=768)
        vector_store = SupabaseVectorStore(
            client=supabase,
            embedding=embeddings,
            table_name="documents",
            query_name="match_documents"
        )
        
        docs = vector_store.similarity_search(query_str, k=3)
        return docs
    except Exception as e:
        print(f"[ERROR] Supabase search failure: {e}")
        return [
            Document(
                page_content=f"Supabase 검색 중 오류가 발생했습니다: {str(e)}",
                metadata={"source": "error"}
            )
        ]

@tool
def web_search(query: str) -> str:
    """인터넷 검색을 수행하여 입력된 쿼리와 관련된 실시간 웹 문서 및 정보를 검색합니다.

    Args:
        query: 검색할 쿼리 또는 질문 문자열
    """
    # Handle direct invocation with args dict
    if isinstance(query, dict):
        query_str = query.get("query", "")
    else:
        query_str = query

    from duckduckgo_search import DDGS
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query_str, max_results=3))
            if not results:
                return f"'{query_str}'에 대한 검색 결과가 없습니다."
            
            formatted_results = []
            for r in results:
                title = r.get("title", "No Title")
                body = r.get("body", r.get("snippet", ""))
                href = r.get("href", "")
                formatted_results.append(f"Title: {title}\nURL: {href}\nContent: {body}\n")
            return "\n".join(formatted_results)
    except Exception as e:
        print(f"[ERROR] Web search failure: {e}")
        return f"인터넷 검색 중 오류가 발생했습니다: {str(e)}"

def add_web_pages_json_to_croma(web_results: list) -> None:
    """웹 검색 결과를 벡터 데이터베이스(Supabase)에 청크로 나누어 저장합니다.

    Args:
        web_results: [{"query": str, "content": str}, ...] 형식의 리스트
    """
    if not web_results:
        return

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if (not supabase_url or not supabase_key or 
        supabase_url == "your_supabase_url_here" or 
        supabase_key == "your_supabase_anon_key_here"):
        print("[WARNING] Supabase credentials are missing. Simulating add_web_pages_json_to_croma.")
        for res in web_results:
            print(f"[Mock DB Save] Query: '{res.get('query')}', Content length: {len(res.get('content', ''))}")
        return

    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        docs = []
        
        for res in web_results:
            query = res.get("query", "")
            content = res.get("content", "")
            if not content.strip():
                continue
            
            chunks = text_splitter.split_text(content)
            for idx, chunk in enumerate(chunks):
                docs.append(
                    Document(
                        page_content=chunk,
                        metadata={"source": "web_search", "query": query, "chunk_id": idx}
                    )
                )

        if not docs:
            print("[INFO] No document chunks to insert into vector DB.")
            return

        supabase = create_client(supabase_url, supabase_key)
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small", dimensions=768)
        vector_store = SupabaseVectorStore(
            client=supabase,
            embedding=embeddings,
            table_name="documents",
            query_name="match_documents"
        )
        
        vector_store.add_documents(docs)
        print(f"[DB Save] Successfully added {len(docs)} chunks from web search to Supabase vector DB.")
    except Exception as e:
        print(f"[ERROR] Failed to save web pages to Supabase vector store: {e}")

