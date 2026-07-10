import os
import io
import time
import base64
from typing import List
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image
import torch
from transformers import CLIPProcessor, CLIPModel
from openai import OpenAI
from dotenv import load_dotenv
from supabase import create_client
import chromadb

# Load environment variables
dotenv_path = r"C:\Anti-project\.env"
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    load_dotenv()

app = FastAPI(
    title="FashionRAG API Server",
    description="FastAPI server for Fashion Multimodal RAG styling helper",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase
def init_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL or SUPABASE_KEY environment variable is missing.")
    return create_client(url, key)

# Initialize ChromaDB
print("Initializing ChromaDBPersistent Client...")
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection("fashion_collection")

# Load CLIP Model
print("Loading CLIP ViT-B/32 model...")
device = "cpu"
model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

# Initialize OpenAI
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Pydantic Schemas
class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    answer: str
    images: List[str]  # Base64 strings of the top 2 fashion images
    db_row_count: int
    retrieval_time_ms: int
    total_time_ms: int

@app.get("/")
def read_root():
    try:
        sb = init_supabase()
        res = sb.table("fashion").select("id", count="exact").limit(1).execute()
        row_count = res.count if res.count is not None else 0
        status = "healthy"
    except Exception as e:
        status = f"error: {str(e)}"
        row_count = 0

    return {
        "status": status,
        "db_row_count": row_count,
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "supabase_configured": bool(os.getenv("SUPABASE_URL"))
    }

@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)):
    start_time = time.time()
    try:
        contents = await file.read()
        pil_img = Image.open(io.BytesIO(contents))
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        
        # Resize to 224x224
        pil_img.thumbnail((224, 224), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        pil_img.save(buffer, format="JPEG", quality=75)
        img_bytes = buffer.getvalue()
        
        # Base64
        base64_str = base64.b64encode(img_bytes).decode("utf-8")
        base64_data = f"data:image/jpeg;base64,{base64_str}"
        
        # CLIP embedding
        inputs = processor(images=pil_img, return_tensors="pt").to(device)
        with torch.no_grad():
            image_features = model.get_image_features(**inputs)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        embedding = image_features[0].cpu().numpy().tolist()
        
        # Save to ChromaDB
        collection.add(
            ids=[file.filename],
            embeddings=[embedding],
            metadatas=[{"image_name": file.filename, "base64_data": base64_data}]
        )
        
        # Save to Supabase
        sb = init_supabase()
        sb.table("fashion").insert({
            "image_name": file.filename,
            "base64_data": base64_data,
            "embedding": embedding
        }).execute()
        
        # Get new row count
        res = sb.table("fashion").select("id", count="exact").execute()
        row_count = res.count if res.count is not None else 0
        
        return {
            "success": True,
            "filename": file.filename,
            "row_count": row_count,
            "elapsed_ms": int((time.time() - start_time) * 1000)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat/query", response_model=QueryResponse)
async def query_fashion(req: QueryRequest):
    overall_start_time = time.time()
    
    # 1. Translate Query: Korean -> English
    try:
        translation_response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional fashion translator. Translate the given Korean fashion styling request into natural, keyword-rich fashion English for image retrieval. Output ONLY the English translation, without quotes, explanations, or labels."},
                {"role": "user", "content": req.query}
            ],
            temperature=0.0
        )
        translated_query = translation_response.choices[0].message.content.strip()
        print(f"Translated query: '{req.query}' -> '{translated_query}'")
    except Exception as e:
        print(f"Translation failed: {e}")
        translated_query = req.query  # Fallback to Korean query
        
    # 2. Vectorize Query using CLIP Text Encoder
    try:
        inputs = processor(text=[translated_query], return_tensors="pt").to(device)
        with torch.no_grad():
            text_features = model.get_text_features(**inputs)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        query_vector = text_features[0].cpu().numpy().tolist()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate query embedding: {str(e)}")
        
    # 3. Retrieve from Supabase (pgvector similarity search)
    retrieval_start = time.time()
    try:
        sb = init_supabase()
        # Fetch total row count first
        count_res = sb.table("fashion").select("id", count="exact").execute()
        db_row_count = count_res.count if count_res.count is not None else 0
        
        # Perform similarity search RPC
        search_res = sb.rpc("match_fashion", {
            "query_embedding": query_vector,
            "match_threshold": 0.0,
            "match_count": 2
        }).execute()
        
        retrieved_items = search_res.data if search_res.data else []
        retretrieval_time_ms = int((time.time() - retrieval_start) * 1000)
        print(f"Retrieved {len(retrieved_items)} items from database. Row count in DB: {db_row_count}")
    except Exception as e:
        # Fallback to local ChromaDB search if Supabase fails (e.g. table doesn't exist yet)
        print(f"Supabase query failed: {e}. Falling back to ChromaDB...")
        retrieval_start = time.time()
        try:
            chroma_res = collection.query(
                query_embeddings=[query_vector],
                n_results=2
            )
            retrieved_items = []
            if chroma_res and chroma_res["metadatas"] and chroma_res["metadatas"][0]:
                for metadata in chroma_res["metadatas"][0]:
                    retrieved_items.append({
                        "image_name": metadata["image_name"],
                        "base64_data": metadata["base64_data"]
                    })
            db_row_count = collection.count()
            retretrieval_time_ms = int((time.time() - retrieval_start) * 1000)
            print(f"Local ChromaDB fallback retrieved {len(retrieved_items)} items. Local count: {db_row_count}")
        except Exception as chroma_err:
            raise HTTPException(status_code=500, detail=f"Database retrieval failed: {str(e)} | Chroma fallback failed: {str(chroma_err)}")
            
    if not retrieved_items:
        raise HTTPException(status_code=404, detail="No fashion images found in the database. Please run ingestion first.")

    # Extract base64 and image names
    retrieved_images = [item["base64_data"] for item in retrieved_items]
    image_names = [item["image_name"] for item in retrieved_items]
    
    # 4. Generate Expert Styling Advice using GPT-4o-mini Vision API in English
    try:
        messages_content = [
            {
                "type": "text",
                "text": (
                    f"User Request: {translated_query}\n\n"
                    "We searched our fashion vector database and retrieved the top 2 matching outfits. "
                    "Please analyze these 2 outfits and write a detailed, professional styling advice in English. "
                    "Explain what these outfits are, why they match the user's request, "
                    "and provide styling tips (such as shoes, accessories, or layering options) "
                    "that will perfect this look."
                )
            }
        ]
        
        for base64_img in retrieved_images:
            # Check if there is data:image prefix, if not, add it
            if not base64_img.startswith("data:image"):
                base64_img = f"data:image/jpeg;base64,{base64_img}"
            messages_content.append({
                "type": "image_url",
                "image_url": {"url": base64_img}
            })
            
        gpt_response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional fashion stylist and coordinate specialist."},
                {"role": "user", "content": messages_content}
            ],
            max_tokens=600,
            temperature=0.7
        )
        english_advice = gpt_response.choices[0].message.content.strip()
        print("Generated English styling advice.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate styling advice: {str(e)}")

    # 5. Translate English Advice -> Korean
    try:
        korean_translation_response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert fashion translator. Translate the given English styling advice into elegant, polite, and natural Korean. Use bullet points and paragraphs to format beautifully. Output ONLY the Korean translation."},
                {"role": "user", "content": english_advice}
            ],
            temperature=0.3
        )
        korean_answer = korean_translation_response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Failed to translate styling advice to Korean: {e}")
        korean_answer = english_advice  # Fallback to English

    total_time_ms = int((time.time() - overall_start_time) * 1000)

    return QueryResponse(
        answer=korean_answer,
        images=retrieved_images,
        db_row_count=db_row_count,
        retrieval_time_ms=retretrieval_time_ms,
        total_time_ms=total_time_ms
    )

@app.post("/api/database/reset")
async def reset_database():
    try:
        # Truncate Supabase fashion table
        sb = init_supabase()
        # Supabase API doesn't support direct truncate, we have to delete all rows with a query
        # Since we want to delete all, we can filter for id > 0
        sb.table("fashion").delete().gt("id", 0).execute()
        
        # Clear ChromaDB collection
        chroma_client.delete_collection("fashion_collection")
        global collection
        collection = chroma_client.create_collection("fashion_collection")
        
        return {"success": True, "message": "Database reset successful."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
