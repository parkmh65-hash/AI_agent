# main.py - ver_02 FastAPI Backend Application

import logging
import json
import httpx
import xml.etree.ElementTree as ET
import urllib.parse
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

async def fetch_national_heritage_openapi(query: str, area_code: str = "전체") -> List[Dict[str, Any]]:
    """Query cultural heritages using official National Heritage Open API"""
    results = []
    search_word = query
    if area_code != "전체" and area_code in query:
        search_word = query.replace(area_code, "").strip()
    if not search_word:
        search_word = query
        
    list_url = f"http://www.cha.go.kr/cha/SearchKindOpenapiList.do?ccbaMnm1={urllib.parse.quote(search_word)}"
    async with httpx.AsyncClient() as client:
        try:
            res_list = await client.get(list_url, timeout=5.0)
            if res_list.status_code == 200:
                root = ET.fromstring(res_list.text)
                items = root.findall(".//item")
                for item in items[:5]:
                    kdcd = item.findtext("ccbaKdcd")
                    asno = item.findtext("ccbaAsno")
                    ctcd = item.findtext("ccbaCtcd")
                    if kdcd and asno and ctcd:
                        dt_url = f"http://www.cha.go.kr/cha/SearchKindOpenapiDt.do?ccbaKdcd={kdcd}&ccbaAsno={asno}&ccbaCtcd={ctcd}"
                        res_dt = await client.get(dt_url, timeout=5.0)
                        if res_dt.status_code == 200:
                            dt_root = ET.fromstring(res_dt.text)
                            dt_item = dt_root.find(".//item")
                            if dt_item is not None:
                                name = dt_item.findtext("ccbaMnm1") or item.findtext("ccbaMnm1")
                                desc = dt_item.findtext("content") or ""
                                lng = dt_item.findtext("longitude")
                                lat = dt_item.findtext("latitude")
                                img = dt_item.findtext("imageUrl")
                                addr = dt_item.findtext("ccbaLcnc") or item.findtext("ccbaLcnc") or ""
                                
                                coord_lat = float(lat) if lat else 0.0
                                coord_lng = float(lng) if lng else 0.0
                                if coord_lat > coord_lng:
                                    latitude = coord_lng
                                    longitude = coord_lat
                                else:
                                    latitude = coord_lat
                                    longitude = coord_lng
                                    
                                if latitude == 0.0 or longitude == 0.0:
                                    latitude = 36.48
                                    longitude = 127.28
                                    
                                results.append({
                                    "id": f"cha_{kdcd}_{asno}_{ctcd}",
                                    "name": name,
                                    "address": addr,
                                    "category": "문화유산",
                                    "era_normalized": "문화재청",
                                    "latitude": latitude,
                                    "longitude": longitude,
                                    "description": desc[:300] + "..." if len(desc) > 300 else desc,
                                    "image_url": img if img and img.startswith("http") else "https://via.placeholder.com/150"
                                })
        except Exception as e:
            logger.error(f"National Heritage API call failed for {search_word}: {e}")
    return results

    # Default Route / Route A: Heritage Search (National Heritage Spatial Information Open API)
    matched = []
    try:
        matched = await fetch_national_heritage_openapi(query, area_code)
    except Exception as e:
        logger.error(f"Failed to query official National Heritage API: {e}")
        
    if len(matched) < 5 and settings.SUPABASE_URL and settings.SUPABASE_KEY:
        try:
            headers = {
                "apikey": settings.SUPABASE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_KEY}"
            }
            safe_query = f"*{query}*"
            url = f"{settings.SUPABASE_URL}/rest/v1/heritages?or=(name.ilike.{safe_query},description.ilike.{safe_query},category.ilike.{safe_query})&limit=5"
            async with httpx.AsyncClient() as client:
                res = await client.get(url, headers=headers, timeout=5.0)
                if res.status_code == 200:
                    raw_list = res.json()
                    for item in raw_list:
                        if not any(m["name"] == item.get("name") for m in matched):
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
                            if len(matched) == 5:
                                break
        except Exception as e:
            logger.error(f"Failed to query backup database for heritages: {e}")

    if len(matched) < 5 and settings.SUPABASE_URL and settings.SUPABASE_KEY:
        try:
            headers = {
                "apikey": settings.SUPABASE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_KEY}"
            }
            url = f"{settings.SUPABASE_URL}/rest/v1/heritages?limit=5"
            async with httpx.AsyncClient() as client:
                res = await client.get(url, headers=headers, timeout=5.0)
                if res.status_code == 200:
                    raw_list = res.json()
                    for item in raw_list:
                        if not any(m["name"] == item.get("name") for m in matched):
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
                            if len(matched) == 5:
                                break
        except Exception:
            pass

    matched = matched[:5]
            
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

# --- DATABASE PROXY ENDPOINTS FOR GOOGLE APPS SCRIPT PLATFORMS ---

class UserProfileRequest(BaseModel):
    email: str
    nickname: str
    auth_provider: Optional[str] = "google"

class ImageUploadRequest(BaseModel):
    base64Data: str
    filename: str

class RecommendationStatusRequest(BaseModel):
    status: str

def get_supabase_headers():
    return {
        "apikey": settings.SUPABASE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_KEY}"
    }

@app.get("/api/v1/db/health")
async def db_health_check():
    """Verify live Supabase connection from FastAPI server"""
    is_working = False
    error_msg = ""
    if settings.SUPABASE_URL and settings.SUPABASE_KEY:
        try:
            headers = get_supabase_headers()
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    f"{settings.SUPABASE_URL}/rest/v1/heritages?select=id&limit=1",
                    headers=headers,
                    timeout=3.0
                )
                if res.status_code == 200:
                    is_working = True
                else:
                    error_msg = f"HTTP {res.status_code}: {res.text}"
        except Exception as e:
            error_msg = str(e)
    else:
        error_msg = "Supabase credentials are not set on the server."
    return {
        "configured": bool(settings.SUPABASE_URL and settings.SUPABASE_KEY),
        "working": is_working,
        "url": settings.SUPABASE_URL,
        "error": error_msg
    }

@app.get("/api/v1/db/initial-data")
async def get_initial_db_data(role: Optional[str] = "user"):
    """Fetch initial application tables data (heritages, citizen_recommendations, and courses)"""
    headers = get_supabase_headers()
    result = {"official": [], "citizen": []}
    if role == "supervisor":
        result["courses"] = []
        
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return result
        
    try:
        async with httpx.AsyncClient() as client:
            # 1. Fetch official heritages
            res_official = await client.get(
                f"{settings.SUPABASE_URL}/rest/v1/heritages?select=*",
                headers=headers,
                timeout=5.0
            )
            if res_official.status_code == 200:
                result["official"] = res_official.json()
            else:
                logger.error(f"Failed to fetch official heritages: {res_official.text}")

            # 2. Fetch citizen recommendations
            citizen_url = f"{settings.SUPABASE_URL}/rest/v1/citizen_recommendations?select=*"
            if role == "supervisor":
                citizen_url += "&order=created_at.desc"
            res_citizen = await client.get(
                citizen_url,
                headers=headers,
                timeout=5.0
            )
            if res_citizen.status_code == 200:
                result["citizen"] = res_citizen.json()
            else:
                logger.error(f"Failed to fetch citizen recommendations: {res_citizen.text}")

            # 3. Fetch courses if supervisor
            if role == "supervisor":
                res_courses = await client.get(
                    f"{settings.SUPABASE_URL}/rest/v1/courses?select=*&order=created_at.desc",
                    headers=headers,
                    timeout=5.0
                )
                if res_courses.status_code == 200:
                    result["courses"] = res_courses.json()
                else:
                    logger.error(f"Failed to fetch courses: {res_courses.text}")
    except Exception as e:
        logger.error(f"Error loading initial DB data: {e}")
        
    return result

@app.post("/api/v1/db/user-profile")
async def upsert_user_profile(req: UserProfileRequest):
    """Upsert user profile configuration in Supabase users_profile table"""
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return {"status": "success", "message": "Local mode bypass (no server credentials)."}
        
    import datetime
    payload = {
        "email": req.email,
        "nickname": req.nickname,
        "auth_provider": req.auth_provider,
        "last_login": datetime.datetime.utcnow().isoformat() + "Z"
    }
    
    headers = get_supabase_headers()
    headers["Content-Type"] = "application/json"
    headers["Prefer"] = "resolution=merge-duplicates"
    
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{settings.SUPABASE_URL}/rest/v1/users_profile",
                headers=headers,
                json=payload,
                timeout=5.0
            )
            if res.status_code in [200, 201]:
                return {"status": "success", "data": res.text}
            else:
                return {"status": "error", "message": res.text}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/v1/db/citizen-recommendation")
async def submit_citizen_recommendation(item: Dict[str, Any]):
    """Insert citizen recommendation item into Supabase"""
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return {"status": "error", "message": "Supabase credentials are not set on the server."}
        
    headers = get_supabase_headers()
    headers["Content-Type"] = "application/json"
    headers["Prefer"] = "return=representation"
    
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{settings.SUPABASE_URL}/rest/v1/citizen_recommendations",
                headers=headers,
                json=item,
                timeout=5.0
            )
            if res.status_code in [200, 201]:
                return {"status": "success", "data": res.json()}
            else:
                return {"status": "error", "message": res.text}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/v1/db/image-upload")
async def upload_image_to_supabase(req: ImageUploadRequest):
    """Decode base64 payload and upload to Supabase storage bucket"""
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return {"status": "error", "message": "Supabase credentials are not set on the server."}
        
    try:
        import base64
        # Clean base64 header if present
        base64_clean = req.base64Data.split(",")[1] if "," in req.base64Data else req.base64Data
        raw_bytes = base64.b64decode(base64_clean)
        
        bucket_name = "heritage-images"
        upload_url = f"{settings.SUPABASE_URL}/storage/v1/object/{bucket_name}/{req.filename}"
        
        headers = get_supabase_headers()
        headers["Content-Type"] = "image/jpeg"
        
        async with httpx.AsyncClient() as client:
            res = await client.post(
                upload_url,
                headers=headers,
                content=raw_bytes,
                timeout=10.0
            )
            if res.status_code in [200, 201]:
                public_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{bucket_name}/{req.filename}"
                return {"status": "success", "publicUrl": public_url}
            else:
                return {"status": "error", "message": res.text}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.patch("/api/v1/db/citizen-recommendation/{rec_id}/status")
async def update_recommendation_status(rec_id: int, req: RecommendationStatusRequest):
    """Vetting status PATCH endpoint for recommendations"""
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return {"status": "error", "message": "Supabase credentials are not set on the server."}
        
    headers = get_supabase_headers()
    headers["Content-Type"] = "application/json"
    
    url = f"{settings.SUPABASE_URL}/rest/v1/citizen_recommendations?id=eq.{rec_id}"
    payload = {"status": req.status}
    
    try:
        async with httpx.AsyncClient() as client:
            res = await client.patch(
                url,
                headers=headers,
                json=payload,
                timeout=5.0
            )
            if res.status_code in [200, 204]:
                return {"status": "success", "id": rec_id, "newStatus": req.status}
            else:
                return {"status": "error", "message": res.text}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/v1/db/stats")
async def get_database_stats():
    """Verify statistics counts for dashboard charts"""
    stats = {"official_count": 0, "citizen_pending": 0, "citizen_approved": 0}
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return stats
        
    headers = get_supabase_headers()
    try:
        async with httpx.AsyncClient() as client:
            # Official count
            res_official = await client.get(
                f"{settings.SUPABASE_URL}/rest/v1/heritages?select=id",
                headers=headers,
                timeout=5.0
            )
            if res_official.status_code == 200:
                stats["official_count"] = len(res_official.json())
                
            # Citizen pending
            res_pending = await client.get(
                f"{settings.SUPABASE_URL}/rest/v1/citizen_recommendations?status=eq.대기&select=id",
                headers=headers,
                timeout=5.0
            )
            if res_pending.status_code == 200:
                stats["citizen_pending"] = len(res_pending.json())
                
            # Citizen approved
            res_approved = await client.get(
                f"{settings.SUPABASE_URL}/rest/v1/citizen_recommendations?status=eq.승인&select=id",
                headers=headers,
                timeout=5.0
            )
            if res_approved.status_code == 200:
                stats["citizen_approved"] = len(res_approved.json())
    except Exception as e:
        logger.error(f"Error loading stats: {e}")
        
    return stats

@app.post("/api/v1/db/official-heritage")
async def insert_official_heritage(item: Dict[str, Any]):
    """Insert official heritage item into Supabase"""
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return {"status": "error", "message": "Supabase credentials are not set on the server."}
        
    headers = get_supabase_headers()
    headers["Content-Type"] = "application/json"
    headers["Prefer"] = "return=representation"
    
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{settings.SUPABASE_URL}/rest/v1/heritages",
                headers=headers,
                json=item,
                timeout=5.0
            )
            if res.status_code in [200, 201]:
                return {"status": "success", "data": res.json()}
            else:
                return {"status": "error", "message": res.text}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class TourSearchRequest(BaseModel):
    query: str
    area_code: Optional[str] = "전체"

@app.post("/api/v1/tour-search")
async def tour_search(req: TourSearchRequest):
    """Retrieve exactly 5 General Tourist attractions matching the region query"""
    matched = []
    area = req.area_code or "세종시"
    
    # 1. Search in citizen_recommendations table
    if settings.SUPABASE_URL and settings.SUPABASE_KEY:
        try:
            headers = get_supabase_headers()
            url = f"{settings.SUPABASE_URL}/rest/v1/citizen_recommendations?address=ilike.*{area}*&limit=10"
            async with httpx.AsyncClient() as client:
                res = await client.get(url, headers=headers, timeout=5.0)
                if res.status_code == 200:
                    raw = res.json()
                    for item in raw:
                        matched.append({
                            "id": f"t_{item.get('id')}",
                            "name": item.get("name"),
                            "address": item.get("address") or "세종특별자치시",
                            "category": "관광지",
                            "latitude": float(item.get("latitude") or 36.50),
                            "longitude": float(item.get("longitude") or 127.26),
                            "description": item.get("description") or "관광공사 연동 관광지 추천 명소입니다.",
                            "image_url": item.get("image_url") or "https://via.placeholder.com/150"
                        })
        except Exception as e:
            logger.error(f"Failed to query citizen recommendations: {e}")
            
    # 2. Korea Tourism Organization KorService1/searchKeyword1 API integration
    import os
    service_key = os.getenv("TOUR_API_KEY") or os.getenv("SERVICE_KEY") or ""
    if len(matched) < 5 and service_key:
        try:
            url = "http://apis.data.go.kr/B551011/KorService1/searchKeyword1"
            query_str = f"{area} {req.query}"
            params = {
                "serviceKey": service_key,
                "numOfRows": 10,
                "pageNo": 1,
                "MobileOS": "ETC",
                "MobileApp": "SejongHeritagePlatform",
                "_type": "json",
                "keyword": query_str,
                "contentTypeId": 12
            }
            async with httpx.AsyncClient() as client:
                res = await client.get(url, params=params, timeout=5.0)
                if res.status_code == 200:
                    data = res.json()
                    items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
                    if isinstance(items, dict):
                        items = [items]
                    for item in items:
                        title = item.get("title")
                        if not title:
                            continue
                        addr = item.get("addr1") or f"{area} 관광지"
                        mapx = item.get("mapx")
                        mapy = item.get("mapy")
                        img = item.get("firstimage") or item.get("firstimage2") or "https://via.placeholder.com/150"
                        
                        if not any(m["name"] == title for m in matched):
                            matched.append({
                                "id": f"kto_{item.get('contentid')}",
                                "name": title,
                                "address": addr,
                                "category": "관광지",
                                "latitude": float(mapy) if mapy else 36.50,
                                "longitude": float(mapx) if mapx else 127.26,
                                "description": f"{title}은(는) 한국관광공사 공인 추천 관광지입니다.",
                                "image_url": img
                            })
                            if len(matched) == 5:
                                break
        except Exception as e:
            logger.error(f"KTO TourAPI call failed: {e}")

    # 3. Static fallback list of Sejong tourist attractions
    if len(matched) < 5:
        sejong_spots = [
            {"name": "세종 베어트리파크", "address": "세종특별자치시 전동면 신송로 217", "latitude": 36.6394, "longitude": 127.2427, "category": "수목원/관광지", "description": "아름다운 나무와 반달곰이 어우러진 친환경 테마 수목원입니다.", "image_url": "https://pdpmtgnagwzcsftavtap.supabase.co/storage/v1/object/public/heritage-images/H1_H1.jpg"},
            {"name": "세종호수공원", "address": "세종특별자치시 다솜로 216", "latitude": 36.5023, "longitude": 127.2861, "category": "공원/호수", "description": "국내 최대의 인공호수공원으로 산책로와 문화행사가 어우러진 휴식공간입니다.", "image_url": "https://pdpmtgnagwzcsftavtap.supabase.co/storage/v1/object/public/heritage-images/H2_H2.jpg"},
            {"name": "국립세종수목원", "address": "세종특별자치시 수목원로 136", "latitude": 36.4950, "longitude": 127.2910, "category": "식물원/수목원", "description": "도심형 수목원으로 거대한 사계절 온실과 전통 정원이 매우 인상적입니다.", "image_url": "https://pdpmtgnagwzcsftavtap.supabase.co/storage/v1/object/public/heritage-images/H3_H3.jpg"},
            {"name": "금강보행교 (이응다리)", "address": "세종특별자치시 세종동 29-111", "latitude": 36.4862, "longitude": 127.2965, "category": "교량/랜드마크", "description": "금강을 가로지르는 국내 최초의 원형 보행교로 야경이 무척 아름답습니다.", "image_url": "https://pdpmtgnagwzcsftavtap.supabase.co/storage/v1/object/public/heritage-images/H4_H4.jpg"},
            {"name": "고복자연공원", "address": "세종특별자치시 연서면 고복리", "latitude": 36.5685, "longitude": 127.2345, "category": "자연/저수지", "description": "벚꽃 길과 데크길 산책로가 조성된 한적하고 평화로운 자연 공원 저수지입니다.", "image_url": "https://via.placeholder.com/150"}
        ]
        for spot in sejong_spots:
            if not any(m["name"] == spot["name"] for m in matched):
                matched.append({
                    "id": f"fallback_{spot['name']}",
                    "name": spot["name"],
                    "address": spot["address"],
                    "category": spot["category"],
                    "latitude": spot["latitude"],
                    "longitude": spot["longitude"],
                    "description": spot["description"],
                    "image_url": spot["image_url"]
                })
                if len(matched) == 5:
                    break
                    
    return {"tourist_spots": matched[:5]}
