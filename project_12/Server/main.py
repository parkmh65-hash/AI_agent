import os
import time
from datetime import datetime
from io import BytesIO
from typing import List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from pypdf import PdfReader

from supabase import create_client
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_community.vectorstores.faiss import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever

# Load environment variables from standard location
dotenv_path = r"C:\Anti-project\.env"
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    load_dotenv()

app = FastAPI(
    title="ChatPDF Advanced RAG API Server",
    description="FastAPI backend for ChatPDF supporting HyDE, Multi Query, Ensemble Retriever, RAG Fusion, and Parent Document",
    version="1.0.0"
)

# Enable CORS for cross-origin frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TABLE_NAME = "documents"
QUERY_NAME = "match_documents"

# Initialize global clients
def init_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or url == "your_supabase_url_here":
        raise ValueError("SUPABASE_URL environment variable is missing or invalid.")
    if not key or key == "your_supabase_anon_key_here":
        raise ValueError("SUPABASE_KEY environment variable is missing or invalid.")
    return create_client(url, key)

# Pydantic schemas
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str
    is_rag: bool
    db_row_count: int
    search_speed_sec: float
    execution_time_sec: float
    generated_queries: List[str]
    hyde_document: str
    timestamp: str

@app.get("/")
def read_root():
    try:
        sb = init_supabase()
        res = sb.table(TABLE_NAME).select("id", count="exact").limit(1).execute()
        row_count = res.count if res.count is not None else 0
        status = "healthy"
    except Exception as e:
        status = f"error: {str(e)}"
        row_count = 0

    return {
        "status": status,
        "db_row_count": row_count,
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY"))
    }

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    start_time = time.time()
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    try:
        sb = init_supabase()
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        vector_store = SupabaseVectorStore(
            client=sb,
            embedding=embeddings,
            table_name=TABLE_NAME,
            query_name=QUERY_NAME
        )

        content = await file.read()
        reader = PdfReader(BytesIO(content))
        num_pages = len(reader.pages)
        
        parent_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
        child_splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=50)
        
        child_documents = []
        for page_idx, page in enumerate(reader.pages):
            text = page.extract_text()
            if not text or not text.strip():
                continue
            
            parent_chunks = parent_splitter.split_text(text)
            for p_idx, parent_chunk in enumerate(parent_chunks):
                child_chunks = child_splitter.split_text(parent_chunk)
                for c_idx, child_chunk in enumerate(child_chunks):
                    doc = Document(
                        page_content=child_chunk,
                        metadata={
                            "source": file.filename,
                            "page": page_idx + 1,
                            "parent_content": parent_chunk,
                            "chunk_id": f"{file.filename}_p{page_idx+1}_parent{p_idx}_child{c_idx}"
                        }
                    )
                    child_documents.append(doc)

        if not child_documents:
            return {"status": "success", "message": "No readable text found in PDF.", "chunks_added": 0}

        # Add to vector store in batches
        batch_size = 50
        for i in range(0, len(child_documents), batch_size):
            batch = child_documents[i:i + batch_size]
            vector_store.add_documents(batch)

        elapsed = time.time() - start_time
        return {
            "status": "success",
            "filename": file.filename,
            "pages": num_pages,
            "chunks_added": len(child_documents),
            "execution_time_sec": elapsed
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF upload and parsing failed: {str(e)}")

def reciprocal_rank_fusion(results_list: List[List[Document]], k: int = 60) -> List[Document]:
    fused_scores = {}
    for docs in results_list:
        for rank, doc in enumerate(docs):
            # Identify document by its chunk_id, falling back to content
            doc_key = doc.metadata.get("chunk_id", doc.page_content)
            if doc_key not in fused_scores:
                fused_scores[doc_key] = {"doc": doc, "score": 0.0}
            fused_scores[doc_key]["score"] += 1.0 / (k + (rank + 1))
            
    # Sort docs by reciprocal rank score
    sorted_docs = sorted(fused_scores.values(), key=lambda x: x["score"], reverse=True)
    return [item["doc"] for item in sorted_docs]

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    overall_start = time.time()
    
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured on the server.")

    sb = init_supabase()
    
    # 1. Get total row count for diagnostics
    db_row_count = 0
    try:
        res = sb.table(TABLE_NAME).select("id", count="exact").limit(1).execute()
        db_row_count = res.count if res.count is not None else 0
    except Exception as e:
        print(f"[Warning] Failed to fetch row count: {e}")

    # 2. Classifier Node: Route (RAG vs General)
    classifier_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    classification_prompt = (
        "당신은 사용자의 질문이 단순 인사, 자기소개, 잡담(예: '안녕', '반가워', '너는 누구니', '오늘 날씨 어때')과 같은 일상적인 대화인지, "
        "아니면 구체적인 지식, 정보, 문서 분석, 내용 확인을 요청하는 질문(RAG)인지 판단하는 분류기입니다.\n"
        "단순 일상 대화인 경우에만 'GENERAL'로 답하고, 그 외 지식이나 정보 검색이 필요해 보이는 모든 질문은 'RAG'로 답하십시오.\n"
        "다른 설명 없이 'GENERAL' 또는 'RAG'로만 대답하십시오.\n\n"
        f"사용자 질문: {request.message}"
    )
    
    try:
        route_reply = classifier_llm.invoke(classification_prompt).content.strip().upper()
        is_rag = "RAG" in route_reply
    except Exception as e:
        print(f"[Warning] Classification failed, defaulting to RAG: {e}")
        is_rag = True

    search_start = time.time()
    generated_queries = []
    hyde_document = ""
    
    if not is_rag or db_row_count == 0:
        # GENERAL flow or empty DB
        search_speed = 0.0
        try:
            general_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
            reply_text = general_llm.invoke(request.message).content
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"General LLM invocation failed: {str(e)}")
    else:
        # RAG flow
        try:
            embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
            
            # Fetch all documents from Supabase to construct BM25 and FAISS in-memory
            # (Ensures real-time indexing of newly uploaded PDFs)
            db_res = sb.table(TABLE_NAME).select("content, metadata").execute()
            db_docs = [
                Document(page_content=item["content"], metadata=item["metadata"])
                for item in db_res.data
            ]
            
            if not db_docs:
                raise ValueError("No documents found in database to build retriever.")
                
            # Build local FAISS and BM25 retrievers
            faiss_vs = FAISS.from_documents(db_docs, embeddings)
            faiss_retriever = faiss_vs.as_retriever(search_kwargs={"k": 5})
            
            bm25_retriever = BM25Retriever.from_documents(db_docs)
            bm25_retriever.k = 5
            
            # Hybrid Search: Ensemble Retriever
            ensemble_retriever = EnsembleRetriever(
                retrievers=[faiss_retriever, bm25_retriever],
                weights=[0.5, 0.5]
            )

            # RAG Step 1: Multi Query Generation
            multiquery_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
            multiquery_prompt = (
                "당신은 AI 언어 모델 조수입니다. 당신의 임무는 주어진 사용자 질문에 대해 벡터 데이터베이스에서 관련 문서를 검색할 수 있도록 다섯 가지 다른 버전을 생성하는 것입니다.\n"
                "사용자 질문에 대한 여러 관점을 생성함으로써, 거리 기반 유사성 검색의 한계를 극복하는 데 도움을 주는 것이 목표입니다.\n"
                "각 질문은 새 줄로 구분하여 제공하세요. 원본 질문: " + request.message
            )
            multiquery_res = multiquery_llm.invoke(multiquery_prompt).content.strip()
            # Split lines and clean
            raw_queries = [line.strip() for line in multiquery_res.split("\n") if line.strip()]
            # Filter out lines that don't look like questions or prefixes
            for q in raw_queries:
                clean_q = q.lstrip("0123456789.-*• ").strip()
                if clean_q:
                    generated_queries.append(clean_q)
            # Ensure at least the original and some variations
            if not generated_queries:
                generated_queries = [request.message]

            # RAG Step 2: HyDE (Hypothetical Document Embeddings)
            hyde_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
            hyde_prompt = (
                "당신은 문서 내용의 답변을 추측해 작성하는 유용한 조수입니다.\n"
                f"주어진 질문 '{request.message}'에 대해, 문서에 있을 법한 가상의 짧은 답변 문단을 한글로 작성해 주세요.\n"
                "문단에 포함될 수 있는 세부적인 사실과 설명을 상상해서 작성하십시오. 다른 설명 없이 가상의 답변 본문만 응답하세요."
            )
            hyde_document = hyde_llm.invoke(hyde_prompt).content.strip()

            # Compile search queries (Original + Multi-queries + HyDE)
            search_queries = [request.message] + generated_queries + [hyde_document]
            
            # RAG Step 3: Run queries through Ensemble Retriever and aggregate results
            all_retrieved_results = []
            for query in search_queries:
                retrieved_docs = ensemble_retriever.invoke(query)
                all_retrieved_results.append(retrieved_docs)

            # RAG Step 4: RAG Fusion (Reciprocal Rank Fusion)
            fused_docs = reciprocal_rank_fusion(all_retrieved_results)

            # RAG Step 5: Parent Document Retrieval mapping
            # (Extract parent_content from child chunk metadata to resolve larger context)
            seen_parent_texts = set()
            context_chunks = []
            for doc in fused_docs[:5]:  # Take top 5 ranked documents
                parent_text = doc.metadata.get("parent_content", doc.page_content)
                if parent_text and parent_text not in seen_parent_texts:
                    seen_parent_texts.add(parent_text)
                    context_chunks.append(parent_text)
            
            context_text = "\n\n".join(context_chunks)
            if not context_text.strip():
                context_text = "[안내: 관련된 문서 내용을 찾지 못했습니다.]"

            search_speed = time.time() - search_start

            # RAG Step 6: Final LLM Generation
            final_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
            final_prompt = (
                "당신은 PDF 문서 분석 비서입니다. 제공된 관련 문서 맥락(Context)을 바탕으로 사용자의 질문에 한국어로 명확하고 상세하게 답변하십시오.\n"
                "답변 시 반드시 참고한 문서 내용에 기반해 답변하고 있다는 점을 명시하고, 제시된 맥락으로 답변이 불가능한 경우 일반 지식으로 보완하되 참고 자료에 해당 내용이 없음을 알려주세요.\n\n"
                f"[Context]\n{context_text}\n\n"
                f"질문: {request.message}\n"
                "답변:"
            )
            reply_text = final_llm.invoke(final_prompt).content

        except Exception as e:
            print(f"[Error in RAG pipeline] {e}")
            # Fallback to general LLM response on failure
            search_speed = time.time() - search_start
            reply_text = f"[주의: RAG 검색 파이프라인 에러 발생. 일반 답변으로 대체합니다. 에러: {str(e)}]\n\n"
            try:
                fallback_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
                reply_text += fallback_llm.invoke(request.message).content
            except Exception as e_inner:
                raise HTTPException(status_code=500, detail=f"RAG pipeline and fallback failed: {str(e_inner)}")

    overall_elapsed = time.time() - overall_start
    timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    return ChatResponse(
        reply=reply_text,
        is_rag=is_rag,
        db_row_count=db_row_count,
        search_speed_sec=search_speed,
        execution_time_sec=overall_elapsed,
        generated_queries=generated_queries,
        hyde_document=hyde_document,
        timestamp=timestamp_str
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
