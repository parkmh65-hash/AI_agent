import os
import shutil
import tempfile
import logging
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List

from app.config import config
from app.models.schemas import QueryRequest, QueryResponse
from app.services.parser import parse_pdf
from app.services.storage import storage_service
from app.services.vectorstore import vector_store_service
from app.services.retriever import retriever_service
from app.services.generator import generator_service

# Import text splitter
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Validate environment config
config.validate_keys()

app = FastAPI(
    title="Multimodal RAG API",
    description="FastAPI backend for processing PDF text, tables, and images, and performing multimodal QA.",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure local directories exist and mount static files for serving local image files
os.makedirs(config.LOCAL_STORAGE_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Multimodal RAG API! Access docs at /docs"}

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Uploads and parses a PDF document, extracts text, tables, and images,
    then indexes their content (Option B: summaries for images) into the vector store.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF documents are supported.")
        
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, file.filename)
    
    try:
        # 1. Save uploaded file to temp path
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        logger.info(f"Received file: {file.filename}. Starting parsing...")
        
        # 2. Parse PDF contents
        parsed_doc = parse_pdf(temp_path)
        
        chunks_to_add = []
        
        # 3. Process Texts
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        
        for text_item in parsed_doc.texts:
            page = text_item["page"]
            text_content = text_item["text"]
            
            split_texts = text_splitter.split_text(text_content)
            for split_t in split_texts:
                chunks_to_add.append({
                    "content": split_t,
                    "metadata": {
                        "source": parsed_doc.filename,
                        "page": page,
                        "type": "text",
                        "original_path": "",
                        "caption": ""
                    }
                })
        
        # 4. Process Tables
        for table_item in parsed_doc.tables:
            page = table_item["page"]
            markdown = table_item["markdown"]
            
            # Generate summary of the table to include in index
            summary = generator_service.generate_table_description(markdown)
            
            chunks_to_add.append({
                "content": f"Table Markdown:\n{markdown}\nTable Summary:\n{summary}",
                "metadata": {
                    "source": parsed_doc.filename,
                    "page": page,
                    "type": "table",
                    "original_path": "",
                    "caption": summary
                }
            })
            
        # 5. Process Images
        for img_item in parsed_doc.images:
            page = img_item["page"]
            img_bytes = img_item["bytes"]
            ext = img_item["ext"]
            name = img_item["name"]
            
            # Upload image to storage (Supabase or Local)
            original_path = storage_service.upload_image(img_bytes, name)
            
            # Generate description using multimodal LLM
            description = generator_service.generate_image_description(img_bytes, ext)
            
            chunks_to_add.append({
                "content": description,
                "metadata": {
                    "source": parsed_doc.filename,
                    "page": page,
                    "type": "image",
                    "original_path": original_path,
                    "caption": description
                }
            })
            
        # 6. Index into Vector Store
        if chunks_to_add:
            vector_store_service.add_documents(chunks_to_add)
            
        logger.info(f"Finished parsing and indexing {file.filename}.")
        
        return {
            "status": "success",
            "filename": parsed_doc.filename,
            "summary": {
                "text_chunks": sum(1 for c in chunks_to_add if c["metadata"]["type"] == "text"),
                "tables": len(parsed_doc.tables),
                "images": len(parsed_doc.images),
                "total_chunks": len(chunks_to_add)
            }
        }
        
    except Exception as e:
        logger.error(f"Error indexing document {file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to index document: {str(e)}")
        
    finally:
        # Cleanup temporary files
        if os.path.exists(temp_path):
            os.remove(temp_path)
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

@app.post("/api/chat/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """
    RAG Query endpoint. First determines routing (chitchat vs RAG), retrieves context if needed,
    profiles performance, and generates a multimodal answer.
    """
    import time
    start_total = time.perf_counter()
    
    try:
        # Convert request history format to dict list for generator service
        history_list = None
        if request.history:
            history_list = [h.dict() for h in request.history]
            
        # 1. Determine routing: chitchat (일상 대화) vs RAG (문서 질의)
        route = retriever_service.determine_routing(request.query)
        
        retrieved_docs = []
        retrieval_time_ms = 0.0
        
        if route == "rag":
            # 2. Retrieve relevant context (with timing)
            start_retrieval = time.perf_counter()
            retrieved_docs = retriever_service.retrieve(
                query_text=request.query,
                top_k=request.top_k,
                filter_dict=request.filter_dict,
                use_multiquery=request.use_multiquery
            )
            retrieval_time_ms = (time.perf_counter() - start_retrieval) * 1000.0
        else:
            logger.info(f"Bypassing retrieval: query '{request.query}' routed as chitchat.")
        
        # 3. Generate answer (with multimodal capabilities)
        answer = generator_service.generate_answer(
            query=request.query,
            retrieved_docs=retrieved_docs,
            history=history_list
        )
        
        # 4. Format sources for response schema
        sources = []
        for doc in retrieved_docs:
            sources.append({
                "content": doc["content"],
                "metadata": {
                    "source": doc["metadata"].get("source", "Unknown"),
                    "page": doc["metadata"].get("page", 0),
                    "type": doc["metadata"].get("type", "text"),
                    "original_path": doc["metadata"].get("original_path", ""),
                    "caption": doc["metadata"].get("caption", "")
                },
                "distance": doc.get("distance", 0.0)
            })
            
        # 5. Measure total execution time
        total_time_ms = (time.perf_counter() - start_total) * 1000.0
        
        performance = {
            "rows_retrieved": len(retrieved_docs),
            "retrieval_time_ms": round(retrieval_time_ms, 2),
            "total_time_ms": round(total_time_ms, 2)
        }
        
        return QueryResponse(answer=answer, sources=sources, performance=performance)
        
    except Exception as e:
        logger.error(f"Error during RAG query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process query: {str(e)}")

@app.post("/api/database/reset")
async def reset_database():
    """
    Resets the vector database (removes all indexed items).
    """
    try:
        vector_store_service.reset_db()
        return {"status": "success", "message": "ChromaDB reset completed."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset database: {str(e)}")
