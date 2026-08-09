# main.py - ver_02 FastAPI Backend Application

import logging
import json
import httpx
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# LangChain / OpenAI imports for Semantic Router & Embeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

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

class QueryRoute(BaseModel):
    target: str = Field(description="선택된 라우팅 경로: 'heritage' (개별 유산 역사/지식) 또는 'course' (코스/경로 추천)")
    rationale: str = Field(description="해당 경로를 선택한 이유")

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

@app.post("/api/v1/agentic-rag")
async def handle_agentic_rag_query(req: RagQueryRequest):
    """Provide RAG optimized recommended cards for Sejong official heritages"""
    query = req.query.strip().lower()
    logger.info(f"Received Agentic RAG Query: {query} (area: {req.area_code})")
    
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    # 1. Semantic Router (LLM Based Routing)
    target_route = "heritage" # default route
    try:
        api_key = settings.OPENAI_API_KEY or "dummy_key"
        llm = ChatOpenAI(model="gpt-4o-mini", openai_api_key=api_key, temperature=0.0)
        parser = JsonOutputParser(pydantic_object=QueryRoute)
        
        prompt = ChatPromptTemplate.from_template(
            "당신은 스마트 관광 플랫폼의 AI 시맨틱 라우터입니다. 사용자의 질문을 분석하여 아래 두 경로 중 하나로 분류해 주세요.\n"
            "1. 'heritage': 특정 문화유산 자체에 대한 지식, 역사, 정보, 유래 등을 묻는 질문 (예: '비암사의 건립 연도는?', '은행나무 역사 알려줘')\n"
            "2. 'course': 여러 장소를 묶은 코스, 여행 경로, 탐방 경로, 갈만한 코스 추천 등을 묻는 질문 (예: '2시간짜리 데이트 코스 짜줘', '아이와 갈만한 코스 추천')\n\n"
            "{format_instructions}\n"
            "질문: {query}"
        )
        
        chain = prompt | llm | parser
        route_decision = await chain.ainvoke({
            "query": query,
            "format_instructions": parser.get_format_instructions()
        })
        target_route = route_decision.get("target", "heritage")
        logger.info(f"Router routed query to: {target_route} (rationale: {route_decision.get('rationale')})")
    except Exception as e:
        logger.warn(f"LLM routing failed, fallback to default 'heritage' route. Error: {e}")

    # 2. Execute Routing Paths
    if target_route == "course" and settings.SUPABASE_URL and settings.SUPABASE_KEY:
        # Route B: Search saved vectorized courses from DB
        recommended_courses = []
        try:
            # Generate embedding query vector
            embeddings_model = OpenAIEmbeddings(openai_api_key=settings.OPENAI_API_KEY)
            query_vector = await embeddings_model.aembed_query(query)
            
            headers = {
                "apikey": settings.SUPABASE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_KEY}",
                "Content-Type": "application/json"
            }
            
            rpc_payload = {
                "query_embedding": query_vector,
                "match_threshold": 0.3,
                "match_count": 3
            }
            
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    f"{settings.SUPABASE_URL}/rest/v1/rpc/match_courses",
                    headers=headers,
                    json=rpc_payload,
                    timeout=5.0
                )
                if res.status_code == 200:
                    recommended_courses = res.json()
        except Exception as e:
            logger.warn(f"Failed to retrieve vector courses from Supabase: {e}")
            
        if recommended_courses:
            matched_heritages = []
            for rc in recommended_courses:
                matched_heritages.append({
                    "id": f"vc_{rc.get('id')}",
                    "name": rc.get("course_name"),
                    "address": f"교통수단: {rc.get('transport')} (총 {rc.get('total_duration')}분)",
                    "category": "추천 저장코스",
                    "description": f"기 생성 융합 코스: {rc.get('description')}",
                    "image_url": "https://pdpmtgnagwzcsftavtap.supabase.co/storage/v1/object/public/heritage-images/H4_H4.jpg"
                })
            return {
                "output_heritages": matched_heritages[:3],
                "final_output": f"AI 분석 결과: 시맨틱 라우팅 결과 '코스 추천'으로 식별되어 과거에 보관된 명소 연계 코스 중 가장 적합한 추천 코스를 발굴했습니다."
            }

    # Default Route / Route A: Heritage Search (Fetch directly from Supabase DB to eliminate dummy list)
    matched = []
    try:
        headers = {
            "apikey": settings.SUPABASE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_KEY}"
        }
        # PostgREST fuzzy keyword matching with 'or' query syntax
        safe_query = f"*{query}*"
        url = f"{settings.SUPABASE_URL}/rest/v1/heritages?or=(name.ilike.{safe_query},description.ilike.{safe_query},category.ilike.{safe_query})"
        
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=headers, timeout=5.0)
            if res.status_code == 200:
                raw_list = res.json()
                for item in raw_list:
                    matched.append({
                        "id": item.get("id") or item.get("h_id") or f"h_{item.get('id')}",
                        "name": item.get("name"),
                        "address": item.get("address") or "세종특별자치시",
                        "category": item.get("category") or "문화유산",
                        "era_normalized": item.get("era_normalized") or "조선시대",
                        "latitude": float(item.get("latitude") or 36.48),
                        "longitude": float(item.get("longitude") or 127.28),
                        "description": item.get("description") or "",
                        "image_url": item.get("image_url") or "https://via.placeholder.com/150"
                    })
    except Exception as e:
        logger.error(f"Failed to query database for heritages: {e}")

    # Fallback to general select if no keyword matches or DB error
    if not matched and settings.SUPABASE_URL and settings.SUPABASE_KEY:
        try:
            url = f"{settings.SUPABASE_URL}/rest/v1/heritages?limit=3"
            async with httpx.AsyncClient() as client:
                res = await client.get(url, headers=headers, timeout=5.0)
                if res.status_code == 200:
                    raw_list = res.json()
                    for item in raw_list:
                        matched.append({
                            "id": item.get("id") or item.get("h_id") or f"h_{item.get('id')}",
                            "name": item.get("name"),
                            "address": item.get("address") or "세종특별자치시",
                            "category": item.get("category") or "문화유산",
                            "era_normalized": item.get("era_normalized") or "조선시대",
                            "latitude": float(item.get("latitude") or 36.48),
                            "longitude": float(item.get("longitude") or 127.28),
                            "description": item.get("description") or "",
                            "image_url": item.get("image_url") or "https://via.placeholder.com/150"
                        })
        except Exception:
            pass
            
    return {
        "output_heritages": matched,
        "final_output": f"AI 분석 결과: 시맨틱 라우팅 결과 '유산 검색'으로 식별되어 원격 데이터베이스 실데이터 실시간 조회를 기반으로 추천 결과를 구성했습니다."
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
