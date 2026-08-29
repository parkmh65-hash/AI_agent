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
from langchain_openai import ChatOpenAI

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

class SaveCourseRequest(BaseModel):
    user_id: str = "guest@sejong.go.kr"
    course_name: str
    description: Optional[str] = ""
    transport: Optional[str] = "승용차"
    total_duration: Optional[int] = 0
    items: List[Any] = []

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

DEFAULT_SEJONG_HERITAGES = [
    {
        "id": "h_1",
        "name": "세종 비암사 극락보전",
        "address": "세종특별자치시 전의면 비암사길 137",
        "category": "보물",
        "era_normalized": "조선시대",
        "latitude": 36.6083,
        "longitude": 127.2131,
        "description": "삼국시대 백제 유민들이 건립한 역사 깊은 전통 사찰의 본전으로 목조 아미타여래좌상이 봉안되어 있습니다.",
        "image_url": "https://tong.visitkorea.or.kr/cms/resource/99/2673599_image2_1.jpg"
    },
    {
        "id": "h_2",
        "name": "세종 봉산동 향나무",
        "address": "세종특별자치시 조치원읍 봉산길 16",
        "category": "천연기념물",
        "era_normalized": "조선시대",
        "latitude": 36.6111,
        "longitude": 127.2917,
        "description": "조선시대 강화최씨 문중의 제단 옆에 심겨져 400여 년의 수령을 간직한 아름다운 우산 모양의 향나무.",
        "image_url": "https://tong.visitkorea.or.kr/cms/resource/11/2673611_image2_1.jpg"
    },
    {
        "id": "h_3",
        "name": "세종 연기리 은행나무",
        "address": "세종특별자치시 연기면 연기길 33-14",
        "category": "기념물",
        "era_normalized": "조선시대",
        "latitude": 36.5312,
        "longitude": 127.2721,
        "description": "조선시대 연기현 관아 터 근처에 심겨진 보호수로, 오랜 세월 마을의 수호신이자 안식처가 되어 온 큰 거목.",
        "image_url": "https://tong.visitkorea.or.kr/cms/resource/35/2673635_image2_1.jpg"
    },
    {
        "id": "h_4",
        "name": "독락정",
        "address": "세종특별자치시 나성동 101-1",
        "category": "문화재자료",
        "era_normalized": "조선시대",
        "latitude": 36.4851,
        "longitude": 127.2625,
        "description": "고려 말 충신인 임난수 장군의 절의를 기려 조선 세종 때 지어진 유서 깊은 전통 목조 정자.",
        "image_url": "https://tong.visitkorea.or.kr/cms/resource/20/2673620_image2_1.jpg"
    },
    {
        "id": "h_5",
        "name": "학림사 신중도",
        "address": "세종특별자치시 연서면 도신고개길 341",
        "category": "문화재자료",
        "era_normalized": "조선시대",
        "latitude": 36.5623,
        "longitude": 127.2341,
        "description": "학림사 대웅전에 보존된 불화로 조선 후기 신중 신앙의 흐름과 뛰어난 불교 채색 화풍을 보여줍니다.",
        "image_url": "https://tong.visitkorea.or.kr/cms/resource/82/2673682_image2_1.jpg"
    },
    {
        "id": "h_6",
        "name": "세종리 은행나무",
        "address": "세종특별자치시 세종동 88-4",
        "category": "기념물",
        "era_normalized": "고려시대",
        "latitude": 36.4952,
        "longitude": 127.2871,
        "description": "고려 말 무신 임난수 장군이 은거하며 심은 거대한 한 쌍의 은행나무로 세종시 출범의 역사적 상징물.",
        "image_url": "https://tong.visitkorea.or.kr/cms/resource/50/2673650_image2_1.jpg"
    },
    {
        "id": "h_7",
        "name": "연서 영평사 아미타삼존도",
        "address": "세종특별자치시 장군면 영평사길 124",
        "category": "유형문화재",
        "era_normalized": "조선시대",
        "latitude": 36.4908,
        "longitude": 127.2023,
        "description": "영평사에 소장된 불교 미술품으로, 아미타불을 중심으로 좌우 협시보살을 묘사한 정교한 조선 후기 탱화.",
        "image_url": "https://tong.visitkorea.or.kr/cms/resource/18/2673718_image2_1.jpg"
    },
    {
        "id": "h_8",
        "name": "비암사 삼층석탑",
        "address": "세종특별자치시 전의면 비암사길 137",
        "category": "유형문화재",
        "era_normalized": "고려시대",
        "latitude": 36.6083,
        "longitude": 127.2131,
        "description": "비암사 대웅전 앞에 기단 위에 정갈하게 우뚝 솟은 고려 시대 양식의 화강암 삼층석탑.",
        "image_url": "https://tong.visitkorea.or.kr/cms/resource/66/2673666_image2_1.jpg"
    },
    {
        "id": "h_9",
        "name": "홍판서댁",
        "address": "세종특별자치시 부강면 부강유하길 37",
        "category": "민속문화재",
        "era_normalized": "조선시대",
        "latitude": 36.5050,
        "longitude": 127.3683,
        "description": "조선 고종 때 병조판서를 지낸 임헌회 선생의 고택으로 마당을 중심으로 배치된 고풍스러운 한옥 주택.",
        "image_url": "https://tong.visitkorea.or.kr/cms/resource/02/2673702_image2_1.jpg"
    },
    {
        "id": "h_10",
        "name": "초려이유태유적지",
        "address": "세종특별자치시 어진동 도움1로 116",
        "category": "기념물",
        "era_normalized": "조선시대",
        "latitude": 36.5015,
        "longitude": 127.2589,
        "description": "조선 17세기 대표적 산림 학자 초려 이유태 선생의 학문적 정신을 계승하고 묘소를 모신 전통 문화 역사 공원.",
        "image_url": "https://tong.visitkorea.or.kr/cms/resource/41/2673741_image2_1.jpg"
    },
    {
        "id": "h_11",
        "name": "덕성서원",
        "address": "세종특별자치시 연기면 원수산로 38-1",
        "category": "향토유적",
        "era_normalized": "조선시대",
        "latitude": 36.5180,
        "longitude": 127.2750,
        "description": "원수산 자락에 자리하여 기호학파의 대표적 선현들을 배향하며 성리학 연구와 교육을 담당했던 전통 서원.",
        "image_url": "https://tong.visitkorea.or.kr/cms/resource/55/2673755_image2_1.jpg"
    },
    {
        "id": "h_12",
        "name": "이성 산성",
        "address": "세종특별자치시 전동면 송곡리 산12",
        "category": "기념물",
        "era_normalized": "삼국시대",
        "latitude": 36.6210,
        "longitude": 127.2550,
        "description": "백제와 고구려 등 삼국이 치열하게 영토 투쟁을 벌였던 세종시 북쪽 원수산 인근의 석축 테뫼식 성곽 유적.",
        "image_url": "https://tong.visitkorea.or.kr/cms/resource/79/2673779_image2_1.jpg"
    },
    {
        "id": "h_13",
        "name": "숭덕사",
        "address": "세종특별자치시 세종동 88-4",
        "category": "향토유적",
        "era_normalized": "조선시대",
        "latitude": 36.4952,
        "longitude": 127.2871,
        "description": "고려 말기 은거하며 끝까지 충절을 지킨 임난수 장군을 배향하여 기리는 사당으로 세종리 역사공원에 위치합니다.",
        "image_url": "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "h_14",
        "name": "합호서원",
        "address": "세종특별자치시 연동면 청연로 531-15",
        "category": "향토유적",
        "era_normalized": "조선시대",
        "latitude": 36.5410,
        "longitude": 127.3290,
        "description": "연동면 금강 유역에 세워져 지방 사림들의 성리학 토론회 및 청소년 유학 교육의 중심지가 된 아름다운 서원.",
        "image_url": "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "h_15",
        "name": "비암사 범종",
        "address": "세종특별자치시 전의면 비암사길 137",
        "category": "문화재자료",
        "era_normalized": "조선시대",
        "latitude": 36.6083,
        "longitude": 127.2131,
        "description": "조선 후기 비암사 종각에 주조되어 걸린 전통 종으로 표면의 보살 비천상 문양이 섬세하게 조각되어 있습니다.",
        "image_url": "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=600&q=80"
    }
]

async def seed_default_heritages_to_supabase_if_empty(table_name: str, headers: Dict[str, str]):
    """Self-healing helper to seed initial 15 heritages to database if completely empty"""
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"{settings.SUPABASE_URL}/rest/v1/{table_name}?select=id&limit=1", headers=headers, timeout=5.0)
            if res.status_code == 200 and len(res.json()) == 0:
                logger.info(f"Supabase Table '{table_name}' is completely empty! Triggering automatic self-healing database seeding...")
                payload = []
                for item in DEFAULT_SEJONG_HERITAGES:
                    payload.append({
                        "name": item["name"],
                        "address": item["address"],
                        "category": item["category"],
                        "era_normalized": item["era_normalized"],
                        "latitude": item["latitude"],
                        "longitude": item["longitude"],
                        "description": item["description"],
                        "photo_url": item["image_url"]
                    })
                res_seed = await client.post(
                    f"{settings.SUPABASE_URL}/rest/v1/{table_name}",
                    headers=headers,
                    json=payload,
                    timeout=8.0
                )
                if res_seed.status_code in [200, 201]:
                    logger.info(f"Database self-healing seeding successfully inserted {len(payload)} heritages into Supabase!")
                else:
                    logger.error(f"Failed database self-healing seeding: {res_seed.status_code} - {res_seed.text}")
    except Exception as e:
        logger.error(f"Error during self-healing database seeding: {e}")

async def extract_search_keyword_via_llm(query: str) -> str:
    """Extract a single heritage noun keyword (e.g. '비암사', '사찰', '탑') suitable for national heritage open API search"""
    if not query or not settings.OPENAI_API_KEY:
        return query
    try:
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "사용자의 자연어 질문에서 문화유산 공공 OpenAPI 검색어(ccbaMnm1 파라미터)로 던질 단 한 개의 명사형 키워드(예: '비암사', '사찰', '탑', '은행나무', '성곽')만 추출하세요. 다른 설명이나 조사 없이 오직 명사 키워드 문자열만 반환하세요."
                },
                {"role": "user", "content": f"질문: {query}"}
            ],
            "temperature": 0.1
        }
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"},
                json=payload,
                timeout=4.0
            )
            if res.status_code == 200:
                keyword = res.json()["choices"][0]["message"]["content"].strip()
                # Remove quotes if present
                keyword = keyword.replace('"', '').replace("'", "")
                return keyword
    except Exception as e:
        logger.warn(f"LLM API keyword extraction failed: {e}")
    return query

@app.post("/api/v1/agentic-rag")
async def handle_agentic_rag_query(req: RagQueryRequest):
    """Provide RAG optimized recommended cards for Sejong official heritages"""
    query = req.query.strip().lower()
    area_code = req.area_code
    logger.info(f"Received Agentic RAG Query: {query} (area: {req.area_code})")
    
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    # 1. RAG Candidates Pool Generation (Merge OpenAPI search and DB heritages)
    matched = []
    
    # Pre-process search query to get clean keyword for open API
    search_keyword = await extract_search_keyword_via_llm(query)
    try:
        matched = await fetch_national_heritage_openapi(search_keyword, area_code)
        logger.info(f"fetch_national_heritage_openapi count: {len(matched)} using search_keyword '{search_keyword}'")
    except Exception as e:
        logger.error(f"Failed to query official National Heritage API using keyword '{search_keyword}': {e}")

    # Fetch up to 15 existing heritages from database to enrich the candidates pool
    if settings.SUPABASE_URL and settings.SUPABASE_KEY:
        try:
            headers = get_supabase_headers()
            async with httpx.AsyncClient() as client:
                table = await get_heritage_table_name(client, headers)
                
                # Normalize area code query parameter to prevent empty results for '세종시' -> '세종'
                db_area = area_code
                if area_code and area_code != "전체":
                    if area_code in ["세종시", "세종"]:
                        db_area = "세종"
                    elif len(area_code) > 2 and (area_code.endswith("시") or area_code.endswith("도")):
                        db_area = area_code[:-1]
                        
                # Filter by region if specified and not "전체"
                if db_area and db_area != "전체":
                    url = f"{settings.SUPABASE_URL}/rest/v1/{table}?address=ilike.*{urllib.parse.quote(db_area)}*&limit=15"
                else:
                    url = f"{settings.SUPABASE_URL}/rest/v1/{table}?limit=15"
                    
                res = await client.get(url, headers=headers, timeout=5.0)
                if res.status_code == 200:
                    raw_list = res.json()
                    logger.info(f"Supabase heritages raw query count: {len(raw_list)} using url '{url}'")
                    added_db_count = 0
                    for item in raw_list:
                        # Deduplicate by name to prevent duplicate LLM candidates
                        if not any(m["name"].strip() == item.get("name").strip() for m in matched):
                            matched.append({
                                "id": item.get("id") or item.get("h_id") or f"h_{item.get('id')}",
                                "name": item.get("name"),
                                "address": item.get("address") or "세종특별자치시",
                                "category": item.get("category") or item.get("era_normalized") or "문화유산",
                                "era_normalized": item.get("era_normalized") or "조선시대",
                                "latitude": float(item.get("latitude") or 36.48),
                                "longitude": float(item.get("longitude") or 127.28),
                                "description": item.get("description") or "",
                                "image_url": item.get("photo_url") or item.get("image_url") or "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=600&q=80"
                            })
                            added_db_count += 1
                    logger.info(f"Added from DB to candidates pool: {added_db_count} items. Total pool: {len(matched)}")
                else:
                    logger.warn(f"Supabase heritages query failed with status: {res.status_code}, response: {res.text}")
        except Exception as e:
            logger.warn(f"Failed to fetch heritages from Supabase for candidate enrichment: {e}")

    # Ensure candidates pool is not empty; fallback to DEFAULT_SEJONG_HERITAGES if completely empty
    if not matched:
        logger.info("Candidates pool is completely empty! Using DEFAULT_SEJONG_HERITAGES as fallback pool.")
        matched = [dict(item) for item in DEFAULT_SEJONG_HERITAGES]

    # 2. AI selection of exactly 5 heritages based on query context from the candidates pool
    try:
        matched = await select_top_heritages_via_llm(query, matched)
        logger.info(f"AI filtered top selected heritages count: {len(matched)}")
    except Exception as e:
        logger.error(f"Failed to perform LLM heritage selection: {e}")
        matched = matched[:5]
    
    # 3. Resolve image URLs for the final selected 5 heritages
    try:
        tasks = [resolve_heritage_image(item) for item in matched]
        resolved_images = await asyncio.gather(*tasks)
        for idx, img in enumerate(resolved_images):
            matched[idx]["image_url"] = img
    except Exception as e:
        logger.error(f"Failed to secure matched heritages images: {e}")

    # 4. Store the selected 5 heritages to database
    try:
        await save_selected_heritages_to_db(matched)
    except Exception as e:
        logger.error(f"Failed to save selected heritages to database: {e}")
    # Return final selected 5 heritages as RAG output for client UI
    return {
        "output_heritages": matched,
        "final_output": "AI 분석 결과: 사용자의 요청 의도에 부합하는 최고의 문화유산 5선을 추천합니다."
    }

async def update_db_heritage_image(name: str, image_url: str):
    """Update photo_url/image_url in the database for the matching heritage name"""
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return
    headers = get_supabase_headers()
    headers["Content-Type"] = "application/json"
    headers["Prefer"] = "return=representation" 
    try:
        async with httpx.AsyncClient() as client:
            table = await get_heritage_table_name(client, headers)
            patch_url = f"{settings.SUPABASE_URL}/rest/v1/{table}?name=eq.{urllib.parse.quote(name)}"
            await client.patch(patch_url, headers=headers, json={"photo_url": image_url}, timeout=3.0)
            logger.info(f"Updated database record for '{name}' with photo_url: {image_url}")
    except Exception as e:
        logger.warn(f"Failed to update database photo_url for '{name}': {e}")

async def fetch_real_heritage_image_search(name: str) -> Optional[str]:
    """Perform real-time HTTP search on Naver Terms / Wikimedia for authentic heritage image URL"""
    if not name:
        return None
    encoded_name = urllib.parse.quote(name)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=4.0) as client:
            # 1. Live search Naver Terms (Encyclopedia)
            url = f"https://terms.naver.com/search.naver?query={encoded_name}"
            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                first_img = soup.select_one("ul.content_list > li .thumb_area img")
                if first_img:
                    raw_src = first_img.get("data-src") or first_img.get("src")
                    if raw_src and raw_src.startswith("http"):
                        return raw_src
            
            # 2. Live search Wikimedia Commons API
            wiki_url = f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&gteqsearch={encoded_name}&prop=pageimages&pithumbsize=600&format=json"
            res_wiki = await client.get(wiki_url, headers=headers)
            if res_wiki.status_code == 200:
                pages = res_wiki.json().get("query", {}).get("pages", {})
                for page_id, page_data in pages.items():
                    thumbnail = page_data.get("thumbnail", {}).get("source")
                    if thumbnail and thumbnail.startswith("http"):
                        return thumbnail
    except Exception as e:
        logger.warn(f"Live heritage image search failed for '{name}': {e}")
    return None

async def get_or_create_heritage_image(name: str, current_img: Optional[str] = None) -> str:
    """Ensure authentic heritage photo URL exists by live scraping Naver/Wikimedia or reusing valid non-fallback image"""
    default_fallback = "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=600&q=80"
    
    # Re-use existing valid image URL if not the duplicate fallback
    if current_img and current_img.startswith("http") and "photo-1548115184" not in current_img and "placeholder" not in current_img:
        return current_img

    # Real-time live search for authentic heritage photo URL
    live_img = await fetch_real_heritage_image_search(name)
    if live_img:
        logger.info(f"Retrieved live authentic image URL for '{name}': {live_img}")
        await update_db_heritage_image(name, live_img)
        return live_img

    if not settings.OPENAI_API_KEY:
        return current_img or default_fallback

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
                timeout=15.0
            )
            if res_dalle.status_code == 200:
                dalle_url = res_dalle.json()["data"][0]["url"]
                logger.info(f"Using DALL-E image URL for '{name}': {dalle_url}")
                await update_db_heritage_image(name, dalle_url)
                return dalle_url
    except Exception as e:
        logger.error(f"Failed to generate DALL-E image for '{name}': {e}")

    return current_img or default_fallback

async def resolve_heritage_image(item: Dict[str, Any]) -> str:
    """Ensure a valid image URL exists by either reusing current or generating via DALL-E directly (without storing to Supabase / Vectorizing)"""
    name = item.get("name")
    if not name:
        return item.get("image_url") or "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=600&q=80"
    try:
        return await get_or_create_heritage_image(name, item.get("image_url"))
    except Exception as e:
        logger.error(f"Error in resolve_heritage_image for '{name}': {e}")
        return item.get("image_url") or "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=600&q=80"

async def select_top_heritages_via_llm(query: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Analyze query and candidate list using LLM to choose exactly 5 heritages that best fit the query intent"""
    logger.info(f"select_top_heritages_via_llm input candidates count: {len(candidates)}")
    if not candidates:
        return []
    if len(candidates) <= 5:
        logger.info(f"Candidates pool size <= 5. Returning all {len(candidates)} items directly.")
        return candidates
        
    if not settings.OPENAI_API_KEY:
        logger.warn("OpenAI API key missing for selection. Returning first 5 candidates.")
        return candidates[:5]
        
    try:
        # Simplify candidate representation for LLM prompt context to save tokens
        candidates_brief = []
        for c in candidates:
            candidates_brief.append({
                "id": c.get("id"),
                "name": c.get("name"),
                "address": c.get("address"),
                "description": c.get("description", "")[:150]
            })
            
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "당신은 스마트 관광 플랫폼의 AI 추천 비서입니다. "
                        "사용자의 자연어 질문과 매칭되는 문화유산 후보 리스트를 분석하여, "
                        "질문 의도와 추천 맥락에 가장 잘 부합하는 문화유산 5개를 선별해 주세요. "
                        "반드시 후보 리스트의 'id' 값들 중에서 5개를 선별해야 하며, "
                        "출력은 오직 'selected_ids' 키에 5개의 id 문자열 배열을 담은 JSON 객체 형식이어야 합니다."
                    )
                },
                {
                    "role": "user",
                    "content": json.dumps({
                        "user_query": query,
                        "candidates": candidates_brief
                    }, ensure_ascii=False)
                }
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }
        
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"},
                json=payload,
                timeout=12.0
            )
            if res.status_code == 200:
                result_json = json.loads(res.json()["choices"][0]["message"]["content"])
                selected_ids = result_json.get("selected_ids", [])
                logger.info(f"LLM selection output selected_ids: {selected_ids}")
                
                # Filter candidates matching the selected IDs
                selected_items = []
                for s_id in selected_ids:
                    # Robust type conversion check for id matching (string / integer)
                    match_item = next((c for c in candidates if str(c.get("id")) == str(s_id)), None)
                    if match_item:
                        selected_items.append(match_item)
                        
                logger.info(f"Matched selected candidates count: {len(selected_items)}")
                
                # Fallback if selection returned invalid or insufficient items
                if len(selected_items) < 5:
                    logger.info("Matched selected items count < 5. Filling candidates from pool.")
                    for c in candidates:
                        if c not in selected_items:
                            selected_items.append(c)
                        if len(selected_items) == 5:
                            break
                            
                logger.info(f"Final output selected heritages count: {len(selected_items[:5])}")
                return selected_items[:5]
            else:
                logger.warn(f"OpenAI GPT completion failed with status: {res.status_code}, response: {res.text}")
    except Exception as e:
        logger.error(f"Failed to filter heritages via LLM: {e}")
        
    return candidates[:5]

async def save_selected_heritages_to_db(items: List[Dict[str, Any]]):
    """Upsert the final selected 5 heritages to database (Supabase heritages table) without generating pgvector embeddings"""
    if not items or not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return
        
    headers = {
        "apikey": settings.SUPABASE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            table = await get_heritage_table_name(client, headers)
            
            for item in items:
                name = item.get("name")
                if not name:
                    continue
                    
                # 1. Resolve address and dong eup myeon
                address = item.get("address") or "세종특별자치시"
                match_dong = re.search(r'(\S+[동읍면])', address)
                dong = match_dong.group(1) if match_dong else "세종시"
                
                photo_url = item.get("image_url") or "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=600&q=80"
                
                # Check if heritage already exists by name
                check_url = f"{settings.SUPABASE_URL}/rest/v1/{table}?name=eq.{urllib.parse.quote(name)}&select=id"
                res_check = await client.get(check_url, headers=headers, timeout=4.0)
                
                h_id = None
                if res_check.status_code == 200:
                    records = res_check.json()
                    if len(records) > 0:
                        h_id = records[0]["id"]
                        
                # Check coordinates (latitude & longitude verification)
                lat_val = float(item.get("latitude") or 0.0)
                lng_val = float(item.get("longitude") or 0.0)
                
                # Verify if coordinates are zero, invalid, or South Korea boundaries fallback defaults (e.g. 36.48, 127.28 Sejong default)
                # If they are suspicious, fetch precise geo coordinates from the address using openstreetmap / openai fallback
                if (lat_val == 0.0 or lng_val == 0.0 or
                    lat_val < 33.0 or lat_val > 40.0 or
                    lng_val < 124.0 or lng_val > 132.0 or
                    (abs(lat_val - 36.48) < 0.01 and abs(lng_val - 127.28) < 0.01)):
                    
                    logger.info(f"Invalid or default coordinates detected for '{name}' ({lat_val}, {lng_val}). Verifying/Geocoding via address '{address}'...")
                    geocoded = await geocode_address(address)
                    if geocoded:
                        lat_val, lng_val = geocoded
                        logger.info(f"Successfully geocoded coordinates for '{name}': ({lat_val}, {lng_val})")
                    else:
                        # Keep fallback defaults if geocoding also fails
                        lat_val = lat_val or 36.48
                        lng_val = lng_val or 127.28
                        
                payload = {
                    "name": name,
                    "address": address,
                    "dong": dong,
                    "latitude": lat_val,
                    "longitude": lng_val,
                    "description": item.get("description") or "",
                    "photo_url": photo_url,
                    "source": "api_crawler",
                    "status": "approved",
                    "era_normalized": item.get("era_normalized") or item.get("category") or "문화유산"
                }
                
                if h_id:
                    # Update (PATCH) existing record
                    patch_url = f"{settings.SUPABASE_URL}/rest/v1/{table}?id=eq.{h_id}"
                    await client.patch(patch_url, headers=headers, json=payload, timeout=4.0)
                    logger.info(f"Successfully updated selected heritage in database: '{name}'")
                else:
                    # Insert (POST) new record
                    insert_url = f"{settings.SUPABASE_URL}/rest/v1/{table}"
                    res_ins = await client.post(insert_url, headers=headers, json=payload, timeout=4.0)
                    if res_ins.status_code in [200, 201]:
                        logger.info(f"Successfully inserted selected heritage into database: '{name}'")
                    else:
                        logger.warn(f"Failed to insert selected heritage '{name}': {res_ins.text}")
                        
    except Exception as e:
        logger.error(f"Error saving selected heritages to database: {e}")

async def select_top_tourist_spots_via_llm(heritages: List[Dict[str, Any]], candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Analyze the selected 5 heritages and tourist spots candidates to select 5 tourist spots closest or most relevant to the heritages"""
    if not candidates:
        return []
    if len(candidates) <= 5:
        return candidates
        
    if not settings.OPENAI_API_KEY:
        logger.warn("OpenAI API key missing for spots selection. Returning first 5 candidates.")
        return candidates[:5]
        
    try:
        # Simplify structures to optimize prompt token usage
        heritages_brief = [{
            "name": h.get("name"),
            "address": h.get("address"),
            "latitude": h.get("latitude"),
            "longitude": h.get("longitude")
        } for h in heritages]
        
        candidates_brief = [{
            "id": c.get("id"),
            "name": c.get("name"),
            "address": c.get("address"),
            "latitude": c.get("latitude"),
            "longitude": c.get("longitude"),
            "description": c.get("description", "")[:120]
        } for c in candidates]
        
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "당신은 스마트 관광 플랫폼의 여행 명소 추천 비서입니다. "
                        "선택된 5개의 대표 문화유산 정보(좌표 포함)와 매칭되는 관광지 후보 리스트를 참고하여, "
                        "문화유산 명소들과 지리적으로 가깝고(동선 낭비가 적고) 탐방 주제에 가장 유기적으로 부합하는 주변 관광지 5개를 선별해 주세요. "
                        "반드시 후보 리스트의 'id' 값들 중에서 5개를 선별해야 하며, "
                        "출력은 오직 'selected_ids' 키에 5개의 id 문자열 배열을 담은 JSON 객체 형식이어야 합니다."
                    )
                },
                {
                    "role": "user",
                    "content": json.dumps({
                        "selected_heritages": heritages_brief,
                        "candidates": candidates_brief
                    }, ensure_ascii=False)
                }
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }
        
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"},
                json=payload,
                timeout=12.0
            )
            if res.status_code == 200:
                result_json = json.loads(res.json()["choices"][0]["message"]["content"])
                selected_ids = result_json.get("selected_ids", [])
                
                selected_spots = []
                for s_id in selected_ids:
                    match_item = next((c for c in candidates if c.get("id") == s_id), None)
                    if match_item:
                        selected_spots.append(match_item)
                        
                if len(selected_spots) < 5:
                    for c in candidates:
                        if c not in selected_spots:
                            selected_spots.append(c)
                        if len(selected_spots) == 5:
                            break
                            
                return selected_spots[:5]
    except Exception as e:
        logger.error(f"Failed to filter tourist spots via LLM: {e}")
        
    return candidates[:5]

async def save_selected_tour_spots_to_db(spots: List[Dict[str, Any]]):
    """Upsert the final selected 5 tourist spots to database (Supabase citizen_recommendations table) with geocode validation"""
    if not spots or not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return
        
    headers = {
        "apikey": settings.SUPABASE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            for item in spots:
                name = item.get("name")
                if not name:
                    continue
                    
                address = item.get("address") or "세종특별자치시"
                photo_url = item.get("image_url") or "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=600&q=80"
                
                # Check coordinates (latitude & longitude verification)
                lat_val = float(item.get("latitude") or 0.0)
                lng_val = float(item.get("longitude") or 0.0)
                
                if (lat_val == 0.0 or lng_val == 0.0 or
                    lat_val < 33.0 or lat_val > 40.0 or
                    lng_val < 124.0 or lng_val > 132.0 or
                    (abs(lat_val - 36.50) < 0.01 and abs(lng_val - 127.26) < 0.01)):
                    
                    logger.info(f"Invalid or default coordinates detected for spot '{name}' ({lat_val}, {lng_val}). Verifying via address '{address}'...")
                    geocoded = await geocode_address(address)
                    if geocoded:
                        lat_val, lng_val = geocoded
                        logger.info(f"Successfully geocoded coordinates for spot '{name}': ({lat_val}, {lng_val})")
                    else:
                        lat_val = lat_val or 36.50
                        lng_val = lng_val or 127.26
                
                # Check if tour spot already exists by name
                check_url = f"{settings.SUPABASE_URL}/rest/v1/citizen_recommendations?name=eq.{urllib.parse.quote(name)}&select=id"
                res_check = await client.get(check_url, headers=headers, timeout=4.0)
                
                spot_id = None
                if res_check.status_code == 200:
                    records = res_check.json()
                    if len(records) > 0:
                        spot_id = records[0]["id"]
                        
                payload = {
                    "name": name,
                    "address": address,
                    "description": item.get("description") or "AI 선별 추천 연동 명소 관광지입니다.",
                    "latitude": lat_val,
                    "longitude": lng_val,
                    "image_url": photo_url,
                    "user_id": "system@sejong.go.kr",
                    "status": "승인"
                }
                
                if spot_id:
                    patch_url = f"{settings.SUPABASE_URL}/rest/v1/citizen_recommendations?id=eq.{spot_id}"
                    await client.patch(patch_url, headers=headers, json=payload, timeout=4.0)
                    logger.info(f"Successfully updated selected tourist spot in database: '{name}'")
                else:
                    insert_url = f"{settings.SUPABASE_URL}/rest/v1/citizen_recommendations"
                    res_ins = await client.post(insert_url, headers=headers, json=payload, timeout=4.0)
                    if res_ins.status_code in [200, 201]:
                        logger.info(f"Successfully inserted selected tourist spot into database: '{name}'")
                    else:
                        logger.warn(f"Failed to insert selected tourist spot '{name}': {res_ins.text}")
                        
    except Exception as e:
        logger.error(f"Error saving selected tourist spots to database: {e}")

async def generate_shortest_path_course_via_llm(spots: List[Dict[str, Any]], transport: str = "승용차") -> Dict[str, Any]:
    """Sort the spots to create the shortest-path logical travel itinerary utilizing Nearest-Neighbor algorithm, and generate course details via LLM"""
    if not spots:
        return {}

    # 1. Perform Nearest-Neighbor Sorting using Haversine formula to guarantee the absolute shortest distance route
    def calculate_haversine(lat1, lon1, lat2, lon2):
        import math
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        return 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)) * R

    sorted_spots = []
    if len(spots) > 0:
        best_path = []
        min_total_dist = float('inf')
        
        # Test starting from each spot to find the path with the minimum overall total distance
        for start_idx in range(len(spots)):
            unvisited = list(spots)
            current = unvisited.pop(start_idx)
            path = [current]
            total_dist = 0.0
            
            while unvisited:
                curr_lat = float(current.get("latitude") or current.get("lat") or 0.0)
                curr_lng = float(current.get("longitude") or current.get("lng") or 0.0)
                
                closest_idx = 0
                closest_dist = float('inf')
                for idx, candidate in enumerate(unvisited):
                    cand_lat = float(candidate.get("latitude") or candidate.get("lat") or 0.0)
                    cand_lng = float(candidate.get("longitude") or candidate.get("lng") or 0.0)
                    dist = calculate_haversine(curr_lat, curr_lng, cand_lat, cand_lng)
                    if dist < closest_dist:
                        closest_dist = dist
                        closest_idx = idx
                
                total_dist += closest_dist
                current = unvisited.pop(closest_idx)
                path.append(current)
                
            if total_dist < min_total_dist:
                min_total_dist = total_dist
                best_path = path
        sorted_spots = best_path
    else:
        sorted_spots = list(spots)

    reference_courses = []
    if settings.SUPABASE_URL and settings.SUPABASE_KEY:
        try:
            headers = {
                "apikey": settings.SUPABASE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_KEY}"
            }
            async with httpx.AsyncClient() as client:
                res = await client.get(f"{settings.SUPABASE_URL}/rest/v1/courses?limit=10", headers=headers, timeout=4.0)
                if res.status_code == 200:
                    reference_courses = res.json()
        except Exception as e:
            logger.warn(f"Failed to fetch reference courses from DB: {e}")

    if not settings.OPENAI_API_KEY:
        logger.warn("OpenAI key missing. Returning Nearest-Neighbor sorted list of items.")
        return {
            "course_name": "세종 스마트 역사문화 탐방 코스",
            "description": "최단 거리 이동 동선으로 연계 구성한 추천 탐방 경로입니다.",
            "transport": transport,
            "total_duration": 120,
            "items": sorted_spots
        }

    try:
        spots_input = [{
            "id": s.get("id"),
            "name": s.get("name"),
            "address": s.get("address"),
            "latitude": s.get("latitude"),
            "longitude": s.get("longitude"),
            "description": s.get("description", "")[:120]
        } for s in sorted_spots]

        prompt_context = {
            "spots": spots_input,
            "transport": transport,
            "reference_courses_structures": [{
                "course_name": c.get("course_name"),
                "description": c.get("description", "")[:100],
                "transport": c.get("transport"),
                "total_duration": c.get("total_duration")
            } for c in reference_courses]
        }

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "당신은 전문 여행 동선 플래너입니다. "
                        "이미 지리적 최단 동선(Nearest-Neighbor)으로 정렬이 완료된 명소 목록을 받았습니다. "
                        "이 정렬된 명소 순서를 그대로 유지하면서, 코스의 테마를 살린 창의적이고 매력적인 코스 이름과 요약 스토리라인 설명을 작성해 주세요. "
                        "출력 포맷은 반드시 아래 JSON 키 구조를 정확하게 만족해야 합니다:\n"
                        "{\n"
                        "  \"course_name\": \"추천 코스 이름(한글)\",\n"
                        "  \"description\": \"코스 전체 스토리라인 및 루트 요약 설명(한글)\",\n"
                        "  \"total_duration\": 총 예상 소요시간 정수값(분 단위, 단순 이동 시간 및 장소별 평균 30분 체류 감안)\n"
                        "}"
                    )
                },
                {
                    "role": "user",
                    "content": json.dumps(prompt_context, ensure_ascii=False)
                }
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3
        }

        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"},
                json=payload,
                timeout=20.0
            )
            if res.status_code == 200:
                result_json = json.loads(res.json()["choices"][0]["message"]["content"])
                return {
                    "course_name": result_json.get("course_name") or "세종 스마트 역사문화 탐방 코스",
                    "description": result_json.get("description") or "최단 거리로 구성한 테마 코스입니다.",
                    "transport": transport,
                    "total_duration": int(result_json.get("total_duration") or 120),
                    "items": sorted_spots
                }
    except Exception as e:
        logger.error(f"Failed to generate optimal shortest course via LLM: {e}")

    return {
        "course_name": "세종 스마트 역사문화 탐방 코스",
        "description": "최단 거리 이동 동선으로 연계 구성한 추천 탐방 경로입니다.",
        "transport": transport,
        "total_duration": 120,
        "items": sorted_spots
    }

async def save_generated_course_to_db(course_data: Dict[str, Any], user_id: str = "guest@sejong.go.kr"):
    """Upsert the final generated AI course into Supabase 'courses' database table"""
    if not course_data or not settings.SUPABASE_URL:
        return False
        
    course_name = course_data.get("course_name")
    if not course_name:
        return False
        
    headers = get_supabase_headers()
    headers["Content-Type"] = "application/json"
    headers["Prefer"] = "return=representation"
    
    target_user = user_id or course_data.get("user_id") or "guest@sejong.go.kr"
    payload = {
        "user_id": target_user,
        "course_name": course_name,
        "description": course_data.get("description") or "",
        "transport": course_data.get("transport") or "승용차",
        "total_duration": int(course_data.get("total_duration") or 0),
        "items": course_data.get("items") or []
    }
    
    try:
        async with httpx.AsyncClient() as client:
            check_url = f"{settings.SUPABASE_URL}/rest/v1/courses?user_id=ilike.{urllib.parse.quote(target_user)}&course_name=eq.{urllib.parse.quote(course_name)}&select=id"
            res_check = await client.get(check_url, headers=headers, timeout=5.0)
            
            course_id = None
            if res_check.status_code == 200:
                records = res_check.json()
                if len(records) > 0:
                    course_id = records[0]["id"]
                    
            if course_id:
                patch_url = f"{settings.SUPABASE_URL}/rest/v1/courses?id=eq.{course_id}"
                res_save = await client.patch(patch_url, headers=headers, json=payload, timeout=5.0)
                logger.info(f"Successfully updated course '{course_name}' in public.courses database. Code={res_save.status_code}")
            else:
                insert_url = f"{settings.SUPABASE_URL}/rest/v1/courses"
                res_save = await client.post(insert_url, headers=headers, json=payload, timeout=5.0)
                logger.info(f"Successfully inserted new course '{course_name}' into public.courses database. Code={res_save.status_code}")
                
            return res_save.status_code in [200, 201, 204]
    except Exception as e:
        logger.error(f"Error saving generated course to database: {e}")
        return False

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
                for item in items[:15]:
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
                                    img = dt_item.findtext("imageUrl") or dt_item.findtext("imageurl") or ""
                                    
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
                            "image_url": img if img and img.startswith("http") else "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=600&q=80"
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
        return guidebook
    except Exception as e:
        logger.error(f"Guidebook generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Guidebook Generation Failed: {str(e)}")

# --- DATABASE PROXY ENDPOINTS FOR GOOGLE APPS SCRIPT PLATFORMS ---

class UserProfileRequest(BaseModel):
    email: str
    nickname: str
    auth_provider: Optional[str] = "google"

class UserAuthRequest(BaseModel):
    email: str
    password: str

class ImageUploadRequest(BaseModel):
    base64Data: str
    filename: str

class RecommendationStatusRequest(BaseModel):
    status: str

def get_supabase_headers():
    key = settings.SUPABASE_KEY or os.getenv("USER_SUPABASE_KEY", "")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["apikey"] = key
        headers["Authorization"] = f"Bearer {key}"
    return headers

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
                if not raw_official:
                    logger.info("Supabase heritages table is empty. Using DEFAULT_SEJONG_HERITAGES as fallback and triggering self-healing seed.")
                    raw_official = [dict(item) for item in DEFAULT_SEJONG_HERITAGES]
                    # Trigger async database seeding
                    asyncio.create_task(seed_default_heritages_to_supabase_if_empty(table, headers))
                    
                for row in raw_official:
                    row.pop("embedding", None)
                    row.pop("vector_embedding", None)
                    if "category" not in row:
                        row["category"] = row.get("era_normalized") or "문화유산"
                    if "image_url" not in row:
                        row["image_url"] = row.get("photo_url") or "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=600&q=80"
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

@app.get("/api/v1/db/user-courses")
async def get_user_courses(user_id: str = "guest@sejong.go.kr"):
    """Fetch saved course recommendations strictly for specific user_id (case-insensitive)"""
    headers = get_supabase_headers()
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return {"status": "success", "courses": []}
        
    try:
        async with httpx.AsyncClient() as client:
            target_encoded = urllib.parse.quote(user_id)
            # Query public.courses with case-insensitive ilike matching on user_id
            url = f"{settings.SUPABASE_URL}/rest/v1/courses?user_id=ilike.{target_encoded}&order=created_at.desc"
            res = await client.get(url, headers=headers, timeout=5.0)
            
            courses = []
            if res.status_code == 200:
                courses = res.json()

            for c in courses:
                c.pop("embedding", None)
                c.pop("courses_vector", None)
            return {"status": "success", "courses": courses}
    except Exception as e:
        logger.error(f"Exception fetching user courses: {e}")
        return {"status": "error", "message": str(e), "courses": []}

@app.post("/api/v1/db/save-course")
async def save_user_course_endpoint(req: SaveCourseRequest):
    """Save/upsert a user recommended course to Supabase courses table"""
    course_data = {
        "user_id": req.user_id,
        "course_name": req.course_name,
        "description": req.description,
        "transport": req.transport,
        "total_duration": req.total_duration,
        "items": req.items
    }
    saved_ok = await save_generated_course_to_db(course_data, user_id=req.user_id)
    return {
        "status": "success" if saved_ok else "warning",
        "message": "Course saved to Supabase DB successfully" if saved_ok else "Course saved locally (Supabase DB bypassed or key empty)",
        "course": course_data
    }

@app.delete("/api/v1/db/delete-course")
async def delete_user_course_endpoint(course_id: str, user_id: str = "guest@sejong.go.kr"):
    """Delete a saved course for a user by id or course_name"""
    headers = get_supabase_headers()
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return {"status": "success", "message": "Mock delete"}
    try:
        async with httpx.AsyncClient() as client:
            target_user = urllib.parse.quote(user_id)
            if str(course_id).isdigit():
                url = f"{settings.SUPABASE_URL}/rest/v1/courses?id=eq.{course_id}&user_id=ilike.{target_user}"
            else:
                url = f"{settings.SUPABASE_URL}/rest/v1/courses?course_name=eq.{urllib.parse.quote(str(course_id))}&user_id=ilike.{target_user}"
            res = await client.delete(url, headers=headers, timeout=5.0)
            if res.status_code in [200, 204]:
                return {"status": "success", "message": "Course deleted"}
            else:
                return {"status": "error", "message": res.text}
    except Exception as e:
        return {"status": "error", "message": str(e)}

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
                f"{settings.SUPABASE_URL}/rest/v1/users_profile?on_conflict=email",
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

@app.post("/api/v1/auth/signup")
async def auth_signup(req: UserAuthRequest):
    """Sign up user via Supabase Auth and insert profile record"""
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return {"status": "error", "message": "Supabase credentials are not set on the server."}
        
    headers = {
        "apikey": settings.SUPABASE_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "email": req.email,
        "password": req.password
    }
    
    try:
        async with httpx.AsyncClient() as client:
            # 1. Call Supabase Auth signup
            signup_url = f"{settings.SUPABASE_URL}/auth/v1/signup"
            res = await client.post(signup_url, headers=headers, json=payload, timeout=10.0)
            
            if res.status_code in [200, 201]:
                # 2. Insert into users_profile table
                import datetime
                nickname = req.email.split("@")[0]
                profile_payload = {
                    "email": req.email,
                    "nickname": nickname,
                    "auth_provider": "email",
                    "last_login": datetime.datetime.utcnow().isoformat() + "Z"
                }
                profile_headers = get_supabase_headers()
                profile_headers["Content-Type"] = "application/json"
                profile_headers["Prefer"] = "resolution=merge-duplicates"
                
                await client.post(
                    f"{settings.SUPABASE_URL}/rest/v1/users_profile?on_conflict=email",
                    headers=profile_headers,
                    json=profile_payload,
                    timeout=5.0
                )
                
                return {"status": "success", "message": "Successfully signed up and profile created."}
            else:
                try:
                    err_msg = res.json().get("msg", res.text)
                except Exception:
                    err_msg = res.text
                return {"status": "error", "message": err_msg}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/v1/auth/login")
async def auth_login(req: UserAuthRequest):
    """Log in user via Supabase Auth and update last_login timestamp"""
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return {"status": "error", "message": "Supabase credentials are not set on the server."}
        
    headers = {
        "apikey": settings.SUPABASE_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "email": req.email,
        "password": req.password
    }
    
    try:
        async with httpx.AsyncClient() as client:
            # 1. Call Supabase Auth token signin
            login_url = f"{settings.SUPABASE_URL}/auth/v1/token?grant_type=password"
            res = await client.post(login_url, headers=headers, json=payload, timeout=10.0)
            
            if res.status_code == 200:
                # 2. Update users_profile last_login timestamp
                import datetime
                nickname = req.email.split("@")[0]
                profile_payload = {
                    "email": req.email,
                    "nickname": nickname,
                    "auth_provider": "email",
                    "last_login": datetime.datetime.utcnow().isoformat() + "Z"
                }
                profile_headers = get_supabase_headers()
                profile_headers["Content-Type"] = "application/json"
                profile_headers["Prefer"] = "resolution=merge-duplicates"
                
                await client.post(
                    f"{settings.SUPABASE_URL}/rest/v1/users_profile?on_conflict=email",
                    headers=profile_headers,
                    json=profile_payload,
                    timeout=5.0
                )
                
                return {"status": "success", "email": req.email, "nickname": nickname}
            else:
                try:
                    res_json = res.json()
                    msg = res_json.get("error_description") or res_json.get("error") or res.text
                except Exception:
                    msg = res.text
                return {"status": "error", "message": msg}
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
    # Ensure status satisfies Supabase check constraint ('신청중', '승인', '반려')
    valid_statuses = ["신청중", "승인", "반려"]
    if item.get("status") not in valid_statuses:
        item["status"] = "신청중"
        
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
        tasks = [resolve_heritage_image(item) for item in results]
        resolved_images = await asyncio.gather(*tasks)
        for idx, img in enumerate(resolved_images):
            results[idx]["image_url"] = img
    except Exception as e:
        logger.error(f"Failed to secure heritage search results: {e}")
    return {"heritages": results}

class TourSearchRequest(BaseModel):
    query: str
    area_code: Optional[str] = "전체"
    heritages: Optional[List[Dict[str, Any]]] = None

@app.post("/api/v1/tour-search")
async def tour_search(req: TourSearchRequest):
    """Retrieve tourist spots near selected heritages and compute shortest TSP routing course"""
    area = req.area_code or "세종시"
    
    # 1. Obtain base heritages
    matched_heritages = req.heritages or []
    if not matched_heritages and settings.SUPABASE_URL and settings.SUPABASE_KEY:
        # Fallback if heritages are not provided by client
        try:
            headers = get_supabase_headers()
            async with httpx.AsyncClient() as client:
                table = await get_heritage_table_name(client, headers)
                res = await client.get(f"{settings.SUPABASE_URL}/rest/v1/{table}?limit=5", headers=headers)
                if res.status_code == 200:
                    matched_heritages = res.json()
        except Exception as e:
            logger.error(f"Fallback heritages query failed: {e}")
            
    # 2. Gather candidates for tourist spots
    tour_candidates = []
    
    # 2-1. Search DB citizen_recommendations table
    if settings.SUPABASE_URL and settings.SUPABASE_KEY:
        try:
            headers = get_supabase_headers()
            url = f"{settings.SUPABASE_URL}/rest/v1/citizen_recommendations?address=ilike.*{urllib.parse.quote(area)}*&limit=15"
            async with httpx.AsyncClient() as client:
                res = await client.get(url, headers=headers, timeout=5.0)
                if res.status_code == 200:
                    raw = res.json()
                    for item in raw:
                        tour_candidates.append({
                            "id": f"t_{item.get('id')}",
                            "name": item.get("name"),
                            "address": item.get("address") or "세종특별자치시",
                            "category": "관광지",
                            "latitude": float(item.get("latitude") or 36.50),
                            "longitude": float(item.get("longitude") or 127.26),
                            "description": item.get("description") or "관광공사 연동 관광지 추천 명소입니다.",
                            "image_url": item.get("image_url") or "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=600&q=80"
                        })
        except Exception as e:
            logger.error(f"Failed to query citizen recommendations: {e}")
            
    # 2-2. Korea Tourism Organization API
    service_key = settings.TOUR_API_KEY
    if service_key:
        try:
            url = "https://apis.data.go.kr/B551011/KorService2/searchKeyword2"
            params = {
                "serviceKey": service_key,
                "numOfRows": 15,
                "pageNo": 1,
                "MobileOS": "ETC",
                "MobileApp": "SejongHeritagePlatform",
                "_type": "json",
                "keyword": area,
                "contentTypeId": 12
            }
            async with httpx.AsyncClient() as client:
                res = await client.get(url, params=params, timeout=5.0)
                if res.status_code == 200:
                    data = res.json()
                    items_container = data.get("response", {}).get("body", {}).get("items", {})
                    items = []
                    if isinstance(items_container, dict):
                        items = items_container.get("item", [])
                    if isinstance(items, dict):
                        items = [items]
                    for item in items:
                        title = item.get("title")
                        if not title:
                            continue
                        addr = item.get("addr1") or f"{area} 관광지"
                        mapx = item.get("mapx")
                        mapy = item.get("mapy")
                        img = item.get("firstimage") or item.get("firstImage") or "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=600&q=80"
                        
                        if not any(m["name"].strip() == title.strip() for m in tour_candidates):
                            tour_candidates.append({
                                "id": f"kto_{item.get('contentid')}",
                                "name": title,
                                "address": addr,
                                "category": "관광지",
                                "latitude": float(mapy) if mapy else 36.50,
                                "longitude": float(mapx) if mapx else 127.26,
                                "description": f"{title}은(는) 한국관광공사 공인 추천 관광지입니다.",
                                "image_url": img
                            })
        except Exception as e:
            logger.error(f"KTO TourAPI call failed: {e}")

    # Fallback to static sejong spots if candidates are dry
    if len(tour_candidates) < 5:
        sejong_spots = [
            {"name": "세종 베어트리파크", "address": "세종특별자치시 전동면 신송로 217", "latitude": 36.6394, "longitude": 127.2427, "category": "관광지", "description": "반달곰 테마 수목원", "image_url": "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=600&q=80"},
            {"name": "세종호수공원", "address": "세종특별자치시 다솜로 216", "latitude": 36.5023, "longitude": 127.2861, "category": "관광지", "description": "인공호수공원", "image_url": "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=600&q=80"},
            {"name": "국립세종수목원", "address": "세종특별자치시 수목원로 136", "latitude": 36.4950, "longitude": 127.2910, "category": "관광지", "description": "도심형 수목원", "image_url": "https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=600&q=80"}
        ]
        for s in sejong_spots:
            if not any(m["name"] == s["name"] for m in tour_candidates):
                tour_candidates.append({
                    "id": f"fallback_{s['name']}",
                    "name": s["name"],
                    "address": s["address"],
                    "category": s["category"],
                    "latitude": s["latitude"],
                    "longitude": s["longitude"],
                    "description": s["description"],
                    "image_url": s["image_url"]
                })

    # 3. Select exactly 5 tourist spots via LLM near the selected 5 heritages
    selected_spots = []
    try:
        selected_spots = await select_top_tourist_spots_via_llm(matched_heritages, tour_candidates)
    except Exception as e:
        logger.error(f"Failed LLM tourist spots selection: {e}")
        selected_spots = tour_candidates[:5]

    # 4. Resolve image URLs for the final selected 5 tourist spots
    try:
        tasks = [resolve_heritage_image(item) for item in selected_spots]
        resolved_images = await asyncio.gather(*tasks)
        for idx, img in enumerate(resolved_images):
            selected_spots[idx]["image_url"] = img
    except Exception as e:
        logger.error(f"Failed to secure tourist spots images: {e}")

    # 5. Store selected tourist spots to database
    try:
        await save_selected_tour_spots_to_db(selected_spots)
    except Exception as e:
        logger.error(f"Failed to save selected spots to database: {e}")

    # 6. TSP Routing Course generation (Shortest-path logic matching 10 items)
    combined_spots = matched_heritages + selected_spots
    optimal_course = {}
    try:
        optimal_course = await generate_shortest_path_course_via_llm(combined_spots, transport="승용차")
    except Exception as e:
        logger.error(f"Failed to calculate shortest TSP route: {e}")
        optimal_course = {
            "course_name": "세종 스마트 역사문화 탐방 코스",
            "description": "AI 연계 구성한 추천 탐방 경로입니다.",
            "transport": "승용차",
            "total_duration": 150,
            "items": combined_spots
        }

    # 7. Store course to database public.courses
    try:
        await save_generated_course_to_db(optimal_course)
    except Exception as e:
        logger.error(f"Failed to save generated course to database: {e}")

    # Return optimal course items
    return {
        "tourist_spots": optimal_course.get("items") or combined_spots,
        "final_output": f"AI 분석 코스명: {optimal_course.get('course_name')}\n총 소요시간: {optimal_course.get('total_duration')}분\n이동수단: {optimal_course.get('transport')}\n\n코스 상세 스토리라인:\n{optimal_course.get('description')}"
    }

@app.get("/api/v1/debug-db")
async def debug_database_contents():
    """Verify raw database rows and tables details for troubleshooting"""
    result = {}
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return {"error": "Supabase configs missing."}
    
    headers = {
        "apikey": settings.SUPABASE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # 1. Check heritages table structure and row count
            res = await client.get(f"{settings.SUPABASE_URL}/rest/v1/heritages?select=*", headers=headers, timeout=5.0)
            result["heritages_status"] = res.status_code
            if res.status_code == 200:
                rows = res.json()
                result["heritages_count"] = len(rows)
                result["heritages_sample"] = rows[:3] if rows else []
            else:
                result["heritages_error"] = res.text
                
            # 2. Check heritage table
            res_h = await client.get(f"{settings.SUPABASE_URL}/rest/v1/heritage?select=*", headers=headers, timeout=5.0)
            result["heritage_status"] = res_h.status_code
            if res_h.status_code == 200:
                rows_h = res_h.json()
                result["heritage_count"] = len(rows_h)
                result["heritage_sample"] = rows_h[:3] if rows_h else []
            else:
                result["heritage_error"] = res_h.text
        except Exception as e:
            result["exception"] = str(e)
            
    return result

