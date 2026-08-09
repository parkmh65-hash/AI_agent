# main.py - ver_02 FastAPI Backend Application

import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.services.guidebook_service import GuidebookService

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ver_02_backend")

app = FastAPI(
    title=settings.APP_NAME,
    description="전국 스마트 문화유산 통합 서비스 백엔드 API 서비스",
    version="2.0.0"
)

# Enable CORS for frontend applications
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Request Schemas
class RagQueryRequest(BaseModel):
    query: str
    area_code: Optional[str] = "전체"

class GuidebookRequest(BaseModel):
    heritages: List[str]
    transport: Optional[str] = "승용차"

# Initialize Guidebook Service
guidebook_service = GuidebookService()

@app.get("/health")
def health_check():
    """Verify server status and DB configurations"""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "supabase_configured": bool(settings.SUPABASE_URL and settings.SUPABASE_KEY),
        "llm_configured": bool(settings.OPENAI_API_KEY or settings.GEMINI_API_KEY)
    }

@app.post("/api/v1/agentic-rag/query")
async def handle_agentic_rag_query(req: RagQueryRequest):
    """Provide RAG optimized recommended cards for Sejong official heritages"""
    query = req.query.strip().lower()
    logger.info(f"Received Agentic RAG Query: {query} (area: {req.area_code})")
    
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
        
    # Simulate database retrieval or basic mock matching for Sejong city heritages
    sejong_heritages = [
        {
            "id": "h_jcw",
            "name": "조치원향교",
            "address": "세종특별자치시 연기면 연기리 32",
            "category": "향교/교육시설",
            "era_normalized": "조선시대",
            "latitude": 36.5982,
            "longitude": 127.2985,
            "description": "조선시대에 조치원 인근의 지방 교육과 인재 양성을 담당했던 유서 깊은 향교입니다.",
            "image_url": "https://pdpmtgnagwzcsftavtap.supabase.co/storage/v1/object/public/heritage-images/H1_H1.jpg"
        },
        {
            "id": "h_bam",
            "name": "비암사",
            "address": "세종특별자치시 전의면 다방리 137",
            "category": "사찰/불교문화",
            "era_normalized": "삼국시대",
            "latitude": 36.6345,
            "longitude": 127.2341,
            "description": "삼국시대에 창건된 고찰로, 극락보전 괘불탱 등 다수의 문화재를 간직한 산사입니다.",
            "image_url": "https://pdpmtgnagwzcsftavtap.supabase.co/storage/v1/object/public/heritage-images/H2_H2.jpg"
        },
        {
            "id": "h_ygam",
            "name": "연기아문",
            "address": "세종특별자치시 연기면 연기리 32",
            "category": "관아/성곽",
            "era_normalized": "조선시대",
            "latitude": 36.5980,
            "longitude": 127.2980,
            "description": "조선시대 관아 부속 전각 중 하나로 정갈한 전통 조형미를 보유하고 있습니다.",
            "image_url": "https://pdpmtgnagwzcsftavtap.supabase.co/storage/v1/object/public/heritage-images/H3_H3.jpg"
        },
        {
            "id": "h_cly",
            "name": "초려역사공원 (초려 이유태)",
            "address": "세종특별자치시 어진동 143",
            "category": "사당/역사공원",
            "era_normalized": "조선시대",
            "latitude": 36.5050,
            "longitude": 127.2512,
            "description": "조선 후기 산림학자 초려 이유태 선생의 학문적 가치를 기리는 역사 테마 공원입니다.",
            "image_url": "https://pdpmtgnagwzcsftavtap.supabase.co/storage/v1/object/public/heritage-images/H4_H4.jpg"
        },
        {
            "id": "h_hgj",
            "name": "합강정",
            "address": "세종특별자치시 연동면 태산로 749",
            "category": "정자/누정",
            "era_normalized": "조선시대",
            "latitude": 36.5218,
            "longitude": 127.3482,
            "description": "금강과 미호천이 합류하는 지점에 위치하여 빼어난 자연 수변경관을 자랑하는 정자입니다.",
            "image_url": "https://pdpmtgnagwzcsftavtap.supabase.co/storage/v1/object/public/heritage-images/H5_H5.jpg"
        }
    ]
    
    # Filter by simple text matching
    matched = [h for h in sejong_heritages if query in h["name"] or query in h["description"] or query in h["category"]]
    if not matched:
        # Fallback to general list if no matches
        matched = sejong_heritages[:3]
        
    return {
        "output_heritages": matched,
        "final_output": f"AI 분석 결과: '{req.query}'에 관련된 역사 문화 코스 5선을 구성했습니다. 지도를 보며 경로를 확인해 보세요."
    }

@app.post("/api/v1/guidebook")
async def generate_travel_guidebook(req: GuidebookRequest):
    """Call the LangChain StateGraph Multi-Agent workflow to create a detailed travel guide"""
    if not req.heritages:
        raise HTTPException(status_code=400, detail="Heritages list cannot be empty.")
    try:
        logger.info(f"Generating guidebook for: {req.heritages} using {req.transport}")
        guidebook = await guidebook_service.create_guidebook(req.heritages, req.transport)
        return guidebook
    except Exception as e:
        logger.error(f"Guidebook generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Guidebook Generation Failed: {str(e)}")
