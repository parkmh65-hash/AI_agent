# main.py - ver_02 FastAPI Backend Application

import logging
import json
import httpx
import re
import asyncio
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

_cached_heritage_table = None

async def get_heritage_table_name(client: httpx.AsyncClient, headers: dict) -> str:
    global _cached_heritage_table
    if _cached_heritage_table is not None:
        return _cached_heritage_table
    if not settings.SUPABASE_URL:
        return "heritages"
    try:
        res = await client.get(
            f"{settings.SUPABASE_URL}/rest/v1/heritages?select=id&limit=1",
            headers=headers,
            timeout=3.0
        )
        if res.status_code != 404:
            _cached_heritage_table = "heritages"
            return "heritages"
    except Exception:
        pass
        
    try:
        res = await client.get(
            f"{settings.SUPABASE_URL}/rest/v1/heritage?select=id&limit=1",
            headers=headers,
            timeout=3.0
        )
        if res.status_code != 404:
            _cached_heritage_table = "heritage"
            return "heritage"
    except Exception:
        pass
        
    return "heritages"

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
    area_code = req.area_code
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
            # Secure, vectorize and store images for course recommendations as well
            try:
                tasks = [upsert_and_vectorize_heritage(item) for item in matched_heritages[:3]]
                resolved_images = await asyncio.gather(*tasks)
                for idx, img in enumerate(resolved_images):
                    matched_heritages[idx]["image_url"] = img
            except Exception as e:
                logger.error(f"Failed to secure/vectorize images for matched courses: {e}")
                
            return {
                "output_heritages": matched_heritages[:3],
                "final_output": f"AI 분석 결과: 시맨틱 라우팅 결과 '코스 추천'으로 식별되어 과거에 보관된 명소 연계 코스 중 가장 적합한 추천 코스를 발굴했습니다."
            }


    # Default Route / Route A: Heritage Search (National Heritage Spatial Information Open API)
    matched = []
    try:
        matched = await fetch_national_heritage_openapi(query, area_code)
    except Exception as e:
        logger.error(f"Failed to query official National Heritage API: {e}")
        
    if len(matched) < 5 and settings.SUPABASE_URL and settings.SUPABASE_KEY and settings.OPENAI_API_KEY:
        try:
            # 1. Generate query embedding of 768 dimensions (for heritages table)
            embed_payload = {
                "input": [query],
                "model": "text-embedding-3-small",
                "dimensions": 768
            }
            query_vector = None
            async with httpx.AsyncClient() as client:
                res_embed = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"},
                    json=embed_payload,
                    timeout=5.0
                )
                if res_embed.status_code == 200:
                    query_vector = res_embed.json()["data"][0]["embedding"]
                    
            if query_vector:
                # 2. Call match_heritages RPC function in Supabase
                headers = {
                    "apikey": settings.SUPABASE_KEY,
                    "Authorization": f"Bearer {settings.SUPABASE_KEY}",
                    "Content-Type": "application/json"
                }
                rpc_payload = {
                    "query_embedding": query_vector,
                    "match_threshold": 0.2,
                    "match_count": 5
                }
                async with httpx.AsyncClient() as client:
                    res = await client.post(
                        f"{settings.SUPABASE_URL}/rest/v1/rpc/match_heritages",
                        headers=headers,
                        json=rpc_payload,
                        timeout=5.0
                    )
                    if res.status_code == 200:
                        raw_list = res.json()
                        for item in raw_list:
                            if not any(m["name"] == item.get("name") for m in matched):
                                matched.append({
                                    "id": item.get("id") or item.get("h_id") or f"h_{item.get('id')}",
                                    "name": item.get("name"),
                                    "address": item.get("address") or "세종특별자치시",
                                    "category": item.get("category") or item.get("era_normalized") or "문화유산",
                                    "era_normalized": item.get("era_normalized") or "조선시대",
                                    "latitude": float(item.get("latitude") or 36.48),
                                    "longitude": float(item.get("longitude") or 127.28),
                                    "description": item.get("description") or "",
                                    "image_url": item.get("photo_url") or item.get("image_url") or "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='150' height='150' viewBox='0 0 150 150'><rect width='100%' height='100%' fill='%23111520'/><path d='M75 35 L35 70 L115 70 Z M45 70 L45 115 L105 115 L105 70 Z' stroke='%2300f5d4' stroke-width='3' fill='none'/></svg>"
                                })
                                if len(matched) >= 5:
                                    break
        except Exception as e:
            logger.error(f"Failed to query semantic vector search database for heritages: {e}")

    if len(matched) < 5 and settings.SUPABASE_URL and settings.SUPABASE_KEY:
        try:
            headers = {
                "apikey": settings.SUPABASE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_KEY}"
            }
            async with httpx.AsyncClient() as client:
                table = await get_heritage_table_name(client, headers)
                url = f"{settings.SUPABASE_URL}/rest/v1/{table}?limit=5"
                res = await client.get(url, headers=headers, timeout=5.0)
                if res.status_code == 200:
                    raw_list = res.json()
                    for item in raw_list:
                        if not any(m["name"] == item.get("name") for m in matched):
                            matched.append({
                                "id": item.get("id") or item.get("h_id") or f"h_{item.get('id')}",
                                "name": item.get("name"),
                                "address": item.get("address") or "세종특별자치시",
                                "category": item.get("category") or item.get("era_normalized") or "문화유산",
                                "era_normalized": item.get("era_normalized") or "조선시대",
                                "latitude": float(item.get("latitude") or 36.48),
                                "longitude": float(item.get("longitude") or 127.28),
                                "description": item.get("description") or "",
                                "image_url": item.get("photo_url") or item.get("image_url") or "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='150' height='150' viewBox='0 0 150 150'><rect width='100%' height='100%' fill='%23111520'/><path d='M75 35 L35 70 L115 70 Z M45 70 L45 115 L105 115 L105 70 Z' stroke='%2300f5d4' stroke-width='3' fill='none'/></svg>"
                            })
                            if len(matched) == 5:
                                break
        except Exception:
            pass

    matched = matched[:5]
    
    # Secure, vectorize and store all matched heritages in database
    try:
        tasks = [upsert_and_vectorize_heritage(item) for item in matched]
        resolved_images = await asyncio.gather(*tasks)
        for idx, img in enumerate(resolved_images):
            matched[idx]["image_url"] = img
    except Exception as e:
        logger.error(f"Failed to secure/vectorize matched heritages: {e}")
            
    return {
        "output_heritages": matched,
        "final_output": f"AI 분석 결과: 시맨틱 라우팅 결과 '유산 검색'으로 식별되어 원격 데이터베이스 실데이터 실시간 조회를 기반으로 추천 결과를 구성했습니다."
    }

async def update_db_heritage_image(name: str, image_url: str):
    """Update photo_url/image_url in the database for the matching heritage name"""
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return
    headers = {
        "apikey": settings.SUPABASE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    try:
        async with httpx.AsyncClient() as client:
            table = await get_heritage_table_name(client, headers)
            patch_url = f"{settings.SUPABASE_URL}/rest/v1/{table}?name=eq.{urllib.parse.quote(name)}"
            await client.patch(patch_url, headers=headers, json={"photo_url": image_url}, timeout=3.0)
            logger.info(f"Updated database record for '{name}' with photo_url: {image_url}")
    except Exception as e:
        logger.warn(f"Failed to update database photo_url for '{name}': {e}")

async def get_or_create_heritage_image(name: str, current_img: Optional[str] = None) -> str:
    """Ensure a valid HTTP photo exists for the spot; generate via DALL-E if missing and save to Supabase bucket"""
    if current_img and current_img.startswith("http") and "placeholder" not in current_img and "svg" not in current_img:
        return current_img
        
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY or not settings.OPENAI_API_KEY:
        return current_img or "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='150' height='150' viewBox='0 0 150 150'><rect width='100%' height='100%' fill='%23111520'/><path d='M75 35 L35 70 L115 70 Z M45 70 L45 115 L105 115 L105 70 Z' stroke='%2300f5d4' stroke-width='3' fill='none'/></svg>"

    safe_name = re.sub(r'[^\w\s]', '', name).strip()
    filename = f"gen_{safe_name.replace(' ', '_')}.jpg"
    public_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/heritage-images/{filename}"

    headers = {
        "apikey": settings.SUPABASE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_KEY}"
    }

    # 1. Check if the image file already exists in Supabase Storage
    try:
        async with httpx.AsyncClient() as client:
            res_head = await client.head(public_url, timeout=3.0)
            if res_head.status_code == 200:
                logger.info(f"Using cached DALL-E image from Supabase storage for '{name}': {public_url}")
                await update_db_heritage_image(name, public_url)
                return public_url
    except Exception as e:
        pass

    # 2. If it does not exist, call OpenAI DALL-E to generate it
    try:
        logger.info(f"Generating DALL-E image for heritage: '{name}'")
        dalle_payload = {
            "model": "dall-e-2",
            "prompt": f"A realistic, beautiful photograph of the cultural heritage site or historic landmark '{name}' in South Korea, daylight, professional travel photography, clear details.",
            "n": 1,
            "size": "512x512"
        }
        async with httpx.AsyncClient() as client:
            res_dalle = await client.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"},
                json=dalle_payload,
                timeout=20.0
            )
            if res_dalle.status_code == 200:
                dalle_url = res_dalle.json()["data"][0]["url"]
                
                # 3. Download the generated image bytes
                res_img = await client.get(dalle_url, timeout=10.0)
                if res_img.status_code == 200:
                    img_bytes = res_img.content
                    
                    # 4. Upload to Supabase Storage
                    upload_url = f"{settings.SUPABASE_URL}/storage/v1/object/heritage-images/{filename}"
                    upload_headers = headers.copy()
                    upload_headers["Content-Type"] = "image/jpeg"
                    
                    res_upload = await client.post(upload_url, headers=upload_headers, content=img_bytes, timeout=10.0)
                    if res_upload.status_code in [200, 201]:
                        logger.info(f"Successfully uploaded generated DALL-E image to storage for '{name}': {public_url}")
                        await update_db_heritage_image(name, public_url)
                        return public_url
    except Exception as e:
        logger.error(f"Failed to generate or upload DALL-E image for '{name}': {e}")

    return current_img or "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='150' height='150' viewBox='0 0 150 150'><rect width='100%' height='100%' fill='%23111520'/><path d='M75 35 L35 70 L115 70 Z M45 70 L45 115 L105 115 L105 70 Z' stroke='%2300f5d4' stroke-width='3' fill='none'/></svg>"

async def get_openai_embedding_768(text: str) -> Optional[List[float]]:
    """Generate 768-dimensional OpenAI embedding for a given text"""
    if not settings.OPENAI_API_KEY:
        return None
    try:
        payload = {
            "input": [text],
            "model": "text-embedding-3-small",
            "dimensions": 768
        }
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"},
                json=payload,
                timeout=10.0
            )
            if res.status_code == 200:
                return res.json()["data"][0]["embedding"]
    except Exception as e:
        logger.error(f"Failed to generate 768-dim embedding: {e}")
    return None

async def upsert_and_vectorize_heritage(item: Dict[str, Any]) -> str:
    """Ensure heritage details are stored, vectorized, and linked to storage photos in Supabase"""
    name = item.get("name")
    if not name:
        return item.get("image_url") or ""
        
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return await get_or_create_heritage_image(name, item.get("image_url"))

    headers = {
        "apikey": settings.SUPABASE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            table = await get_heritage_table_name(client, headers)
            
            # 1. Check if the heritage already exists
            check_url = f"{settings.SUPABASE_URL}/rest/v1/{table}?name=eq.{urllib.parse.quote(name)}&select=id,photo_url,embedding"
            res_check = await client.get(check_url, headers=headers, timeout=5.0)
            
            existing_record = None
            if res_check.status_code == 200:
                records = res_check.json()
                if len(records) > 0:
                    existing_record = records[0]

            # 2. Get or generate the image URL
            current_photo = existing_record.get("photo_url") if existing_record else item.get("image_url")
            photo_url = await get_or_create_heritage_image(name, current_photo)
            
            # 3. If it already exists, update missing fields
            if existing_record:
                h_id = existing_record["id"]
                updates = {}
                
                if existing_record.get("photo_url") != photo_url:
                    updates["photo_url"] = photo_url
                    
                if not existing_record.get("embedding"):
                    desc = item.get("description") or ""
                    text_to_embed = f"문화유산명: {name}\n소재지: {item.get('address') or ''}\n설명: {desc}"
                    vector = await get_openai_embedding_768(text_to_embed)
                    if vector:
                        updates["embedding"] = vector
                        
                if updates:
                    patch_url = f"{settings.SUPABASE_URL}/rest/v1/{table}?id=eq.{h_id}"
                    await client.patch(patch_url, headers=headers, json=updates, timeout=5.0)
                    logger.info(f"Updated existing heritage '{name}' with missing fields: {list(updates.keys())}")
                    
                return photo_url
                
            # 4. If completely new, insert it
            else:
                desc = item.get("description") or ""
                text_to_embed = f"문화유산명: {name}\n소재지: {item.get('address') or ''}\n설명: {desc}"
                
                # Generate 768-dimensional embedding
                vector = await get_openai_embedding_768(text_to_embed)
                
                # Extract 'dong' to satisfy NOT NULL constraints
                address = item.get("address") or "세종특별자치시"
                match_dong = re.search(r'(\S+[동읍면])', address)
                dong = match_dong.group(1) if match_dong else "세종시"
                
                new_item = {
                    "name": name,
                    "address": address,
                    "dong": dong,
                    "latitude": item.get("latitude") or 36.48,
                    "longitude": item.get("longitude") or 127.28,
                    "description": desc,
                    "photo_url": photo_url,
                    "source": "api_crawler",
                    "status": "approved",
                    "era_normalized": item.get("era_normalized") or item.get("category") or "문화유산"
                }
                
                if vector:
                    new_item["embedding"] = vector
                    
                insert_url = f"{settings.SUPABASE_URL}/rest/v1/{table}"
                headers_ins = headers.copy()
                headers_ins["Prefer"] = "return=representation"
                
                res_ins = await client.post(insert_url, headers=headers_ins, json=new_item, timeout=5.0)
                if res_ins.status_code in [200, 201]:
                    logger.info(f"Successfully vectorized and inserted new heritage into database: '{name}'")
                else:
                    logger.warn(f"Failed to insert new heritage '{name}': {res_ins.text}")
                    
                return photo_url

    except Exception as e:
        logger.error(f"Error in upsert_and_vectorize_heritage for '{name}': {e}")
        
    return item.get("image_url") or ""

async def geocode_address(address: str) -> Optional[tuple[float, float]]:
    """Geocode address using OpenStreetMap Nominatim, with OpenAI fallback"""
    if not address:
        return None
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # 1. Try Nominatim with full address
    try:
        async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
            url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(address)}&format=json"
            res = await client.get(url, headers=headers, timeout=4.0)
            if res.status_code == 200:
                data = res.json()
                if len(data) > 0:
                    return float(data[0]['lat']), float(data[0]['lon'])
    except Exception as e:
        logger.warning(f"Nominatim geocode failed for full address: {e}")
        
    # 2. Try Nominatim with simplified address
    parts = address.split()
    if len(parts) > 3:
        simple_addr = " ".join(parts[:3])
        try:
            async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
                url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(simple_addr)}&format=json"
                res = await client.get(url, headers=headers, timeout=4.0)
                if res.status_code == 200:
                    data = res.json()
                    if len(data) > 0:
                        return float(data[0]['lat']), float(data[0]['lon'])
        except Exception as e:
            logger.warning(f"Nominatim geocode failed for simplified address: {e}")

    # 3. Fallback to OpenAI gpt-4o-mini geocoding
    if settings.OPENAI_API_KEY:
        try:
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system", 
                        "content": (
                            "You are a precise geographic geocoding assistant for South Korea. "
                            "For the given address, find its coordinates (latitude and longitude). "
                            "Do not return default center coordinates unless absolutely necessary. "
                            "Output strictly a JSON object with keys 'latitude' and 'longitude' as floats."
                        )
                    },
                    {"role": "user", "content": f"Address: {address}"}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.0
            }
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=5.0
                )
                if res.status_code == 200:
                    result = res.json()
                    content = json.loads(result["choices"][0]["message"]["content"])
                    lat = float(content.get("latitude", 0.0))
                    lng = float(content.get("longitude", 0.0))
                    if lat != 0.0 and lng != 0.0:
                        return lat, lng
        except Exception as e:
            logger.error(f"OpenAI fallback geocoding failed: {e}")
            
    return None

async def fetch_national_heritage_openapi(query: str, area_code: str = "전체") -> List[Dict[str, Any]]:
    """Query cultural heritages combining SearchKindOpenapiList, SearchKindOpenapiDt, and Heritage GIS APIs"""
    results = []
    
    # Sido code mapping for Korea
    REGIONS_MAP = {
        "서울": "11", "서울특별시": "11",
        "부산": "21", "부산광역시": "21",
        "대구": "22", "대구광역시": "22",
        "인천": "23", "인천광역시": "23",
        "광주": "24", "광주광역시": "24",
        "대전": "25", "대전광역시": "25",
        "울산": "26", "울산광역시": "26",
        "세종": "45", "세종특별자치시": "45",
        "경기": "31", "경기도": "31",
        "강원": "32", "강원특별자치도": "32",
        "충북": "33", "충청북도": "33",
        "충남": "34", "충청남도": "34",
        "전북": "35", "전라북도": "35", "전북특별자치도": "35",
        "전남": "36", "전라남도": "36",
        "경북": "37", "경상북도": "37",
        "경남": "38", "경상남도": "38",
        "제주": "50", "제주특별자치도": "50"
    }
    
    ctcd = ""
    if area_code != "전체":
        ctcd = REGIONS_MAP.get(area_code, "")
        if not ctcd:
            for k, v in REGIONS_MAP.items():
                if k in area_code or area_code in k:
                    ctcd = v
                    break

    search_word = query
    if area_code != "전체" and area_code in query:
        search_word = query.replace(area_code, "").strip()
    if not search_word:
        search_word = query
        
    # 1. Query List API (SearchKindOpenapiList.do)
    list_url = f"http://www.khs.go.kr/cha/SearchKindOpenapiList.do?ccbaMnm1={urllib.parse.quote(search_word)}"
    if ctcd:
        list_url += f"&ccbaCtcd={ctcd}"
        
    async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
        try:
            res_list = await client.get(list_url, timeout=6.0)
            if res_list.status_code == 200:
                root = ET.fromstring(res_list.text)
                items = root.findall(".//item")
                for item in items[:5]:
                    kdcd_val = item.findtext("ccbaKdcd")
                    asno_val = item.findtext("ccbaAsno")
                    ctcd_val = item.findtext("ccbaCtcd")
                    
                    if kdcd_val and asno_val and ctcd_val:
                        # Default values from list item
                        name = item.findtext("ccbaMnm1") or ""
                        addr = item.findtext("ccbaLcnc") or ""
                        list_lng = item.findtext("longitude")
                        list_lat = item.findtext("latitude")
                        
                        desc = ""
                        img = ""
                        
                        # 2. Query Detail API (SearchKindOpenapiDt.do)
                        dt_url = f"http://www.khs.go.kr/cha/SearchKindOpenapiDt.do?ccbaKdcd={kdcd_val}&ccbaAsno={asno_val}&ccbaCtcd={ctcd_val}"
                        try:
                            res_dt = await client.get(dt_url, timeout=5.0)
                            if res_dt.status_code == 200:
                                dt_root = ET.fromstring(res_dt.text)
                                dt_item = dt_root.find(".//item")
                                if dt_item is not None:
                                    name = dt_item.findtext("ccbaMnm1") or name
                                    desc = dt_item.findtext("content") or ""
                                    img = dt_item.findtext("imageUrl") or ""
                                    
                                    ccbaLcad = dt_item.find("ccbaLcad")
                                    if ccbaLcad is not None:
                                        addr = "".join(ccbaLcad.itertext()).strip()
                        except Exception as e:
                            logger.warn(f"Detail API failed for {kdcd_val}-{asno_val}: {e}")
                            
                        # Extract coordinates (Detail API priority, then List API, then GIS API fallback)
                        lng_val = 0.0
                        lat_val = 0.0
                        
                        # Try to parse detail XML coordinates first if present in root
                        dt_lng = dt_root.findtext("longitude") if 'dt_root' in locals() else None
                        dt_lat = dt_root.findtext("latitude") if 'dt_root' in locals() else None
                        
                        coord_lng = dt_lng or list_lng
                        coord_lat = dt_lat or list_lat
                        
                        if coord_lng and coord_lng != "0":
                            lng_val = float(coord_lng)
                        if coord_lat and coord_lat != "0":
                            lat_val = float(coord_lat)
                            
                        # 3. Fallback to GIS Location API (spca.do) if coordinates are zero/invalid
                        if lng_val == 0.0 or lat_val == 0.0:
                            gis_url = f"https://gis-heritage.go.kr/openapi/xmlService/spca.do?ccbaKdcd={kdcd_val}&ccbaAsno={asno_val}&ccbaCtcd={ctcd_val}"
                            try:
                                res_gis = await client.get(gis_url, timeout=5.0)
                                if res_gis.status_code == 200:
                                    gis_root = ET.fromstring(res_gis.text)
                                    gis_item = gis_root.find(".//item")
                                    if gis_item is not None:
                                        gis_lng = gis_item.findtext("longitude")
                                        gis_lat = gis_item.findtext("latitude")
                                        if gis_lng and gis_lng != "0":
                                            lng_val = float(gis_lng)
                                        if gis_lat and gis_lat != "0":
                                            lat_val = float(gis_lat)
                            except Exception as e:
                                logger.warn(f"GIS API failed for {kdcd_val}-{asno_val}: {e}")
                                
                        # Coordinate normalization / swap check
                        if lat_val > lng_val:
                            latitude = lng_val
                            longitude = lat_val
                        else:
                            latitude = lat_val
                            longitude = lng_val
                            
                        if latitude == 0.0 or longitude == 0.0 or (latitude == 36.48 and longitude == 127.28):
                            geocoded = await geocode_address(addr)
                            if geocoded:
                                latitude, longitude = geocoded
                            else:
                                latitude = 36.48
                                longitude = 127.28
                            
                        results.append({
                            "id": f"cha_{kdcd_val}_{asno_val}_{ctcd_val}",
                            "name": name,
                            "address": addr,
                            "category": "문화유산",
                            "era_normalized": "국가유산청",
                            "latitude": latitude,
                            "longitude": longitude,
                            "description": desc[:300] + "..." if len(desc) > 300 else desc,
                            "image_url": img if img and img.startswith("http") else "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='150' height='150' viewBox='0 0 150 150'><rect width='100%' height='100%' fill='%23111520'/><path d='M75 35 L35 70 L115 70 Z M45 70 L45 115 L105 115 L105 70 Z' stroke='%2300f5d4' stroke-width='3' fill='none'/></svg>"
                        })
        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            logger.error(f"Combined Heritage APIs call failed for {search_word}: {e}\n{tb_str}")
            
    return results

@app.post("/api/v1/guidebook")
async def generate_travel_guidebook(req: GuidebookRequest):
    """Call the LangChain StateGraph Multi-Agent workflow to create a detailed travel guide and cache results in pgvector db"""
    if not req.heritages:
        raise HTTPException(status_code=400, detail="Heritages list cannot be empty.")
    try:
        logger.info(f"Generating guidebook for: {req.heritages} using {req.transport}")
        guidebook = await guidebook_service.create_guidebook(req.heritages, req.transport)
        
        # Async RAG Caching / Vectorization to courses_vector database
        if settings.SUPABASE_URL and settings.SUPABASE_KEY and settings.OPENAI_API_KEY:
            try:
                story_content = guidebook.get("final_output", {}).get("story_result", "") or ""
                course_name = " -> ".join(req.heritages)
                embedding_text = f"코스명: {course_name}\n이동수단: {req.transport}\n가이드북 본문: {story_content}"
                
                embeddings_model = OpenAIEmbeddings(openai_api_key=settings.OPENAI_API_KEY)
                course_vector = await embeddings_model.aembed_query(embedding_text)
                
                headers = {
                    "apikey": settings.SUPABASE_KEY,
                    "Authorization": f"Bearer {settings.SUPABASE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal"
                }
                
                cards = guidebook.get("final_output", {}).get("cards", [])
                total_duration = guidebook.get("final_output", {}).get("total_duration", 0)
                
                payload = {
                    "course_name": course_name,
                    "description": story_content[:500] + "..." if len(story_content) > 500 else story_content,
                    "transport": req.transport,
                    "total_duration": total_duration,
                    "items": cards,
                    "embedding": course_vector
                }
                
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"{settings.SUPABASE_URL}/rest/v1/courses_vector",
                        headers=headers,
                        json=payload,
                        timeout=5.0
                    )
                    logger.info("Successfully vectorized and cached generated course in public.courses_vector.")
            except Exception as cache_err:
                logger.warn(f"Failed to cache generated course into pgvector database: {cache_err}")
                
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
                table = await get_heritage_table_name(client, headers)
                res = await client.get(
                    f"{settings.SUPABASE_URL}/rest/v1/{table}?select=id&limit=1",
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
            table = await get_heritage_table_name(client, headers)
            res_official = await client.get(
                f"{settings.SUPABASE_URL}/rest/v1/{table}?select=*",
                headers=headers,
                timeout=5.0
            )
            if res_official.status_code == 200:
                raw_official = res_official.json()
                for row in raw_official:
                    row.pop("embedding", None)
                    row.pop("vector_embedding", None)
                    if "category" not in row:
                        row["category"] = row.get("era_normalized") or "문화유산"
                    if "image_url" not in row:
                        row["image_url"] = row.get("photo_url") or "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='150' height='150' viewBox='0 0 150 150'><rect width='100%' height='100%' fill='%23111520'/><path d='M75 35 L35 70 L115 70 Z M45 70 L45 115 L105 115 L105 70 Z' stroke='%2300f5d4' stroke-width='3' fill='none'/></svg>"
                result["official"] = raw_official
            else:
                logger.error(f"Failed to fetch official heritages: {res_official.text}")

            # 2. Fetch citizen recommendations
            citizen_url = f"{settings.SUPABASE_URL}/rest/v1/citizen_recommendations?select=*"
            if role == "supervisor":
                citizen_url += "&order=submitted_at.desc"
            res_citizen = await client.get(
                citizen_url,
                headers=headers,
                timeout=5.0
            )
            if res_citizen.status_code == 200:
                raw_citizen = res_citizen.json()
                for row in raw_citizen:
                    row.pop("embedding", None)
                    row.pop("vector_embedding", None)
                    if "created_at" not in row:
                        row["created_at"] = row.get("submitted_at")
                    # Normalize '신청중' to '대기' for frontend vetting controls
                    if row.get("status") == "신청중":
                        row["status"] = "대기"
                result["citizen"] = raw_citizen
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
                    raw_courses = res_courses.json()
                    for row in raw_courses:
                        row.pop("embedding", None)
                        row.pop("vector_embedding", None)
                        row.pop("course_vector", None)
                        row.pop("courses_vector", None)
                        row.pop("route_vector", None)
                    result["courses"] = raw_courses
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
    
    # Geocode citizen address before insertion if coords are missing or default
    address = item.get("address") or ""
    lat = item.get("latitude")
    lng = item.get("longitude")
    if address and (not lat or not lng or (lat == 36.48 and lng == 127.28) or (lat == 0.0 or lng == 0.0)):
        geocoded = await geocode_address(address)
        if geocoded:
            item["latitude"] = geocoded[0]
            item["longitude"] = geocoded[1]
            
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
async def update_recommendation_status(rec_id: str, req: RecommendationStatusRequest):
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
            table = await get_heritage_table_name(client, headers)
            res_official = await client.get(
                f"{settings.SUPABASE_URL}/rest/v1/{table}?select=id",
                headers=headers,
                timeout=5.0
            )
            if res_official.status_code == 200:
                stats["official_count"] = len(res_official.json())
                
            # Citizen pending
            res_pending = await client.get(
                f"{settings.SUPABASE_URL}/rest/v1/citizen_recommendations?or=(status.eq.대기,status.eq.신청중)&select=id",
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
    
    # Extract 'dong' to satisfy NOT NULL constraint in database
    address = item.get("address") or ""
    dong = item.get("dong")
    if not dong:
        match_dong = re.search(r'(\S+[동읍면])', address)
        dong = match_dong.group(1) if match_dong else "세종시"

    # Map input keys to heritages table schema
    cleaned_item = {
        "h_id": item.get("h_id"),
        "name": item.get("name"),
        "address": address,
        "dong": dong,
        "latitude": item.get("latitude"),
        "longitude": item.get("longitude"),
        "description": item.get("description"),
        "photo_url": item.get("image_url") or item.get("photo_url"),
        "source": item.get("source", "registered"),
        "status": item.get("status", "approved"),
        "era_normalized": item.get("era_normalized") or item.get("category") or "문화유산",
    }
    
    # Overwrite coordinates using geocoding if they are missing or default
    lat = cleaned_item.get("latitude")
    lng = cleaned_item.get("longitude")
    if not lat or not lng or (lat == 36.48 and lng == 127.28) or (lat == 0.0 or lng == 0.0):
        geocoded = await geocode_address(address)
        if geocoded:
            cleaned_item["latitude"] = geocoded[0]
            cleaned_item["longitude"] = geocoded[1]
    
    try:
        async with httpx.AsyncClient() as client:
            table = await get_heritage_table_name(client, headers)
            res = await client.post(
                f"{settings.SUPABASE_URL}/rest/v1/{table}",
                headers=headers,
                json=cleaned_item,
                timeout=5.0
            )
            if res.status_code in [200, 201]:
                return {"status": "success", "data": res.json()}
            else:
                return {"status": "error", "message": res.text}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/v1/heritage-search")
async def heritage_search(query: str, area_code: Optional[str] = "전체"):
    """Search heritages directly using official National Heritage Open API"""
    results = await fetch_national_heritage_openapi(query, area_code)
    try:
        tasks = [upsert_and_vectorize_heritage(item) for item in results]
        resolved_images = await asyncio.gather(*tasks)
        for idx, img in enumerate(resolved_images):
            results[idx]["image_url"] = img
    except Exception as e:
        logger.error(f"Failed to secure/vectorize heritage search results: {e}")
    return {"heritages": results}

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
                            "image_url": item.get("image_url") or "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='150' height='150' viewBox='0 0 150 150'><rect width='100%' height='100%' fill='%23111520'/><path d='M75 35 L35 70 L115 70 Z M45 70 L45 115 L105 115 L105 70 Z' stroke='%2300f5d4' stroke-width='3' fill='none'/></svg>"
                        })
        except Exception as e:
            logger.error(f"Failed to query citizen recommendations: {e}")
            
    # 2. Korea Tourism Organization (한국관광공사_국문 관광정보 서비스_GW) integration
    service_key = settings.TOUR_API_KEY
    if len(matched) < 5 and service_key:
        try:
            # 코스 생성 및 주변 관광지 정보 조회를 위한 외부 API로는 오직 '한국관광공사_국문 관광정보 서비스_GW' (KorService2/searchKeyword2)만 사용
            url = "https://apis.data.go.kr/B551011/KorService2/searchKeyword2"
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
                    items_container = data.get("response", {}).get("body", {}).get("items", {})
                    if isinstance(items_container, dict):
                        items = items_container.get("item", [])
                    else:
                        items = []
                    if isinstance(items, dict):
                        items = [items]
                    for item in items:
                        title = item.get("title")
                        if not title:
                            continue
                        addr = item.get("addr1") or f"{area} 관광지"
                        mapx = item.get("mapx")
                        mapy = item.get("mapy")
                        img = item.get("firstimage") or item.get("firstimage2") or "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='150' height='150' viewBox='0 0 150 150'><rect width='100%' height='100%' fill='%23111520'/><path d='M75 35 L35 70 L115 70 Z M45 70 L45 115 L105 115 L105 70 Z' stroke='%2300f5d4' stroke-width='3' fill='none'/></svg>"
                        
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
            {"name": "고복자연공원", "address": "세종특별자치시 연서면 고복리", "latitude": 36.5685, "longitude": 127.2345, "category": "자연/저수지", "description": "벚꽃 길과 데크길 산책로가 조성된 한적하고 평화로운 자연 공원 저수지입니다.", "image_url": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='150' height='150' viewBox='0 0 150 150'><rect width='100%' height='100%' fill='%23111520'/><path d='M75 35 L35 70 L115 70 Z M45 70 L45 115 L105 115 L105 70 Z' stroke='%2300f5d4' stroke-width='3' fill='none'/></svg>"}
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
                    
    spots = matched[:5]
    try:
        tasks = [upsert_and_vectorize_heritage(item) for item in spots]
        resolved_images = await asyncio.gather(*tasks)
        for idx, img in enumerate(resolved_images):
            spots[idx]["image_url"] = img
    except Exception as e:
        logger.error(f"Failed to secure/vectorize tourist spots: {e}")
    return {"tourist_spots": spots}
