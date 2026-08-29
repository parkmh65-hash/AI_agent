import os
import re
import math
import logging
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query, Header, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("heritage_backend")

app = FastAPI(
    title="Smart Cultural Heritage Exploration Platform API",
    description="Backend API for Heritage Exploration, RAG AI Course Recommendation, Supabase Integration with Auto-Pruning Retry, and Nominatim Geocoding.",
    version="1.0.0"
)

# Enable CORS for all origins (GAS iframe, local web app, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration from Environment Variables
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Standard In-Memory Storage Fallback (Used if Supabase is unconfigured)
MEMORY_CITIZEN_DB: List[Dict[str, Any]] = [
    {
        "id": 1,
        "title": "세종 조천 연꽃공원 문화쉼터",
        "address": "세종특별자치시 조치원읍 번암리 1-1",
        "reason": "봄·여름 생태 문화유산과 생태 조천 산책로가 인상적인 시민 추천 명소",
        "photo_url": "https://images.unsplash.com/photo-1542601906990-b4d3fb778b09?w=600&auto=format&fit=crop",
        "submitted_by": "시민탐방대원",
        "lat": 36.598,
        "lng": 127.302,
        "created_at": "2026-08-01T10:00:00Z"
    }
]

MEMORY_USER_COURSES: List[Dict[str, Any]] = []

# Initial Official Cultural Heritage Dataset
OFFICIAL_HERITAGES: List[Dict[str, Any]] = [
    {
        "id": "h-101",
        "name": "세종 비암사 극락보전",
        "category": "보물 / 유형문화유산",
        "address": "세종특별자치시 전의면 비암사길 137",
        "lat": 36.6432,
        "lng": 127.2023,
        "image_url": "https://images.unsplash.com/photo-1548013146-72479768bada?w=800&auto=format&fit=crop",
        "description": "백제 구류선왕 시대 창건된 고찰로, 극락보전 내부에는 계유명전씨아미타불비상(국보 제106호) 등 무수한 문화재 역사가 숨쉬고 있습니다.",
        "tags": ["사찰", "국보역사", "호젓한산책", "전의면"],
        "audio_script": "비암사는 세종시 전의면에 위치한 천년 고찰입니다. 극락보전은 고풍스러운 목조건축의 대명사로 백제의 유민들이 조상의 넋을 기리기 위해 세운 사찰로 알려져 있습니다."
    },
    {
        "id": "h-102",
        "name": "세종 숭모각 (임난수 사당)",
        "category": "기념물 / 역사유적",
        "address": "세종특별자치시 연기면 세종리 88-1",
        "lat": 36.4950,
        "lng": 127.2835,
        "image_url": "", # Intentionally empty to showcase "📷 이미지 없음" fallback badge
        "description": "고려 말 충신 임난수 장군을 배향한 사당으로, 세종시의 고유 충절 역사와 영나무(은행나무 세종시 기념물)의 자태를 볼 수 있습니다.",
        "tags": ["충절유적", "은행나무", "연기면", "역사탐방"],
        "audio_script": "숭모각은 고려 삼사좌윤을 지낸 임난수 장군의 절의를 기리는 사당입니다. 백성들과 함께 이 땅을 개간하여 터전을 닦은 숭고한 충절의 정신을 기립니다."
    },
    {
        "id": "h-103",
        "name": "세종 금강보행교 (이응다리) & 금강 역사권",
        "category": "세종 현대·자연 문화유산",
        "address": "세종특별자치시 보람동 3-7",
        "lat": 36.4789,
        "lng": 127.2891,
        "image_url": "https://images.unsplash.com/photo-1519501025264-65ba15a82390?w=800&auto=format&fit=crop",
        "description": "세종대왕의 한글 창제 정신(반지름 463m, 한글 세종대왕 1446년 상징)을 담은 국내 최초 복층 금강 순환형 보행교입니다.",
        "tags": ["한글건축", "야경명소", "금강권", "가족탐방"],
        "audio_script": "금강보행교 이응다리는 세종대왕의 훈민정음 반포 연도인 1446년을 상징하는 1446미터의 둘레를 자랑합니다. 금강의 비경과 세종시의 현대적 야경이 조화를 이룹니다."
    },
    {
        "id": "h-104",
        "name": "세종 초수지 (전의 초수)",
        "category": "기념물 / 의약역사유적",
        "address": "세종특별자치시 전의면 관정리 149",
        "lat": 36.6710,
        "lng": 127.2180,
        "image_url": "", # Intentionally empty image URL
        "description": "세종대왕의 눈병을 치료한 신비의 탄산 약수터로, 조선왕조실록에도 기록된 세종시 명천(名泉) 문화유산입니다.",
        "tags": ["세종대왕약수", "탄산초수", "전의면", "힐링유적"],
        "audio_script": "전의 초수는 조선 세종 26년, 세종대왕의 안질을 고치기 위해 왕실로 진상되었던 신비의 천연 탄산 약수터입니다."
    },
    {
        "id": "h-105",
        "name": "공주 공산성 (백제역사유적지구)",
        "category": "사적 / 세계유네스코유산",
        "address": "충청남도 공주시 웅진로 280",
        "lat": 36.4608,
        "lng": 127.1264,
        "image_url": "https://images.unsplash.com/photo-1578637387939-43c525550085?w=800&auto=format&fit=crop",
        "description": "백제 웅진성 시대를 대표하는 도성 산성으로, 금강 변을 따라 뻗은 성곽길과 요새 산성의 웅장함을 느낄 수 있습니다.",
        "tags": ["세계유산", "백제웅진성", "금강산성", "역사기행"],
        "audio_script": "공산성은 백제 웅진 시대의 왕성이자 조선 시대까지 충청 감영의 주요 성곽 역할을 한 유네스코 세계유산입니다."
    },
    {
        "id": "h-106",
        "name": "공주 무령왕릉과 왕릉원",
        "category": "사적 / 세계유네스코유산",
        "address": "충청남도 공주시 왕릉로 37",
        "lat": 36.4605,
        "lng": 127.1121,
        "image_url": "https://images.unsplash.com/photo-1509114397022-ed747cca3f65?w=800&auto=format&fit=crop",
        "description": "백제 제25대 무령왕과 왕비의 무덤으로, 도굴되지 않은 상태로 발견되어 무수한 금제 관식과 지석이 출토된 백제 문화의 정수입니다.",
        "tags": ["백제왕릉", "무령왕", "유네스코", "고분군"],
        "audio_script": "무령왕릉은 백제의 피라미드로 불리는 백제 문화의 대명사입니다. 삼국시대 왕릉 중 주인이 확인된 유일한 왕릉입니다."
    },
    {
        "id": "h-107",
        "name": "세종 국립세종수목원 한국전통정원",
        "category": "세종 문화생태유산",
        "address": "세종특별자치시 수목원로 136",
        "lat": 36.4965,
        "lng": 127.2941,
        "image_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800&auto=format&fit=crop",
        "description": "조선시대 창덕궁 후원 솔바람길과 창경궁 아미산 정원의 아름다움을 재현한 한국 전통 정원 건축 조경 유산입니다.",
        "tags": ["전통정원", "창덕궁재현", "생태자연", "가족휴식"],
        "audio_script": "국립세종수목원 내 한국전통정원은 조선시대 대표 궁궐 정원의 양식을 정교하게 복원한 문화 조경 공간입니다."
    },
    {
        "id": "h-108",
        "name": "세종 합강정 (금강·미호강 두물머리)",
        "category": "세종 명승자연유산",
        "address": "세종특별자치시 동면 용호리 43-1",
        "lat": 36.5168,
        "lng": 127.3421,
        "image_url": "", # Intentionally empty image URL
        "description": "금강과 미호강이 어우러지는 세종시 대표 두물머리로, 예로부터 시인 묵객들이 정자를 지어 풍류를 읊던 명승지입니다.",
        "tags": ["두물머리", "정자풍류", "생태습지", "노을명소"],
        "audio_script": "합강정은 금강과 미호강 두 물줄기가 만나는 절경을 한눈에 바라볼 수 있는 세종시 대표 풍류 정자입니다."
    }
]

# --- Helper Algorithms & Distance Functions ---

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points in kilometers."""
    R = 6371.0 # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def solve_tsp_nearest_neighbor(start_coord: Dict[str, float], items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Solves Traveling Salesperson Problem (TSP) using Nearest-Neighbor Greedy Algorithm.
    Returns ordered items, step-by-step route coordinates, and cumulative distance.
    """
    if not items:
        return {"ordered_items": [], "total_distance_km": 0.0, "route_coords": []}
    
    unvisited = list(items)
    curr_lat = start_coord.get("lat", 36.50)
    curr_lng = start_coord.get("lng", 127.26)
    
    ordered = []
    total_dist = 0.0
    route_coords = [[curr_lat, curr_lng]]
    
    order_idx = 1
    while unvisited:
        best_idx = 0
        best_dist = float('inf')
        
        for i, item in enumerate(unvisited):
            i_lat = item.get("lat", 36.50)
            i_lng = item.get("lng", 127.26)
            d = haversine_distance(curr_lat, curr_lng, i_lat, i_lng)
            if d < best_dist:
                best_dist = d
                best_idx = i
        
        closest_item = unvisited.pop(best_idx)
        closest_item_copy = dict(closest_item)
        closest_item_copy["tsp_order"] = order_idx
        closest_item_copy["distance_from_prev_km"] = round(best_dist, 2)
        
        total_dist += best_dist
        curr_lat = closest_item.get("lat", 36.50)
        curr_lng = closest_item.get("lng", 127.26)
        
        ordered.append(closest_item_copy)
        route_coords.append([curr_lat, curr_lng])
        order_idx += 1
        
    return {
        "ordered_items": ordered,
        "total_distance_km": round(total_dist, 2),
        "route_coords": route_coords
    }

# --- Supabase REST API & PGRST204 Auto-Pruning Engine ---

async def post_to_supabase_with_auto_prune(table_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inserts a record into Supabase REST PostgREST API with auto-pruning retry logic.
    If Supabase returns PGRST204 (unknown column), parses error message, removes invalid column key,
    and retries up to 3 times automatically.
    """
    if not SUPABASE_URL or not SUPABASE_KEY or not SUPABASE_URL.startswith("http"):
        logger.warning("Supabase credentials not configured or invalid URL. Using memory database fallback.")
        return {"status": "memory_fallback", "payload": payload}

    endpoint = f"{SUPABASE_URL}/rest/v1/{table_name}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    current_payload = dict(payload)
    max_retries = 3

    async with httpx.AsyncClient(timeout=5.0) as client:
        for attempt in range(max_retries):
            try:
                response = await client.post(endpoint, json=current_payload, headers=headers)
                if response.status_code in (200, 201):
                    res_data = response.json()
                    return {"status": "success", "data": res_data}
                
                err_body = response.text
                logger.warning(f"Supabase POST attempt {attempt+1} failed ({response.status_code}): {err_body}")

                # Check for PGRST204 error (missing column in schema)
                if "PGRST204" in err_body or "Could not find the" in err_body or "column" in err_body.lower():
                    col_match = re.search(r"'(?:([a-zA-Z0-9_]+))'\s+column", err_body, re.IGNORECASE)
                    if not col_match:
                        col_match = re.search(r"column\s+'?([a-zA-Z0-9_]+)'?", err_body, re.IGNORECASE)

                    if col_match:
                        bad_column = col_match.group(1)
                        if bad_column in current_payload:
                            logger.info(f"Auto-Pruning Engine: Removing invalid column '{bad_column}' from payload and retrying...")
                            current_payload.pop(bad_column)
                            continue

                break
            except Exception as e:
                logger.error(f"HTTP Exception during Supabase POST: {str(e)}")
                break

    return {"status": "fallback_exec", "payload": current_payload}

async def geocode_with_nominatim(address: str) -> Dict[str, float]:
    """Geocodes an address string using OpenStreetMap Nominatim REST API with fallback."""
    if not address or len(address.strip()) == 0:
        return {"lat": 36.50, "lng": 127.26}

    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1}
    headers = {"User-Agent": "HeritageExplorerApp/1.0 (contact: info@heritage.sejong.kr)"}

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            res = await client.get(url, params=params, headers=headers)
            if res.status_code == 200:
                data = res.json()
                if data and len(data) > 0:
                    return {
                        "lat": float(data[0]["lat"]),
                        "lng": float(data[0]["lon"])
                    }
    except Exception as e:
        logger.warning(f"Nominatim geocoding fallback triggered: {e}")

    return {"lat": 36.50, "lng": 127.26}

# --- Request / Response Models ---

class RAGQueryRequest(BaseModel):
    prompt: str = Field(..., description="User query or theme for tour exploration")
    user_lat: Optional[float] = Field(36.50, description="User current latitude")
    user_lng: Optional[float] = Field(127.26, description="User current longitude")
    category_filter: Optional[str] = Field("전체", description="Category filter pill")

class CitizenRecommendationInput(BaseModel):
    title: str = Field(..., description="Name of heritage or spot")
    address: str = Field(..., description="Address of the spot")
    # Dual field support for request flexibility
    reason: Optional[str] = Field(None, description="Reason for recommendation")
    description: Optional[str] = Field(None, description="Description fallback key")
    photo_url: Optional[str] = Field(None, description="Photo URL")
    image_url: Optional[str] = Field(None, description="Image URL fallback key")
    submitted_by: Optional[str] = Field("시민탐방대원", description="User or submitter name")
    user_id: Optional[str] = Field(None, description="User ID fallback key")
    lat: Optional[float] = None
    lng: Optional[float] = None

class UserCourseInput(BaseModel):
    course_name: str = Field(..., description="Title of the customized course")
    heritage_ids: List[str] = Field(..., description="List of heritage IDs included in course")
    user_id: Optional[str] = Field("guest_user", description="Owner user ID")
    total_distance_km: Optional[float] = 0.0

# --- API Endpoints ---

@app.get("/")
async def serve_index():
    """Serves the Single Page Application HTML frontend."""
    return FileResponse("index.html")

@app.get("/api/v1/db/initial-data")
async def get_initial_data():
    """
    Returns official heritage dataset and citizen recommendations.
    Attempts Supabase fetch first, falling back to rich static dataset.
    """
    citizen_list = list(MEMORY_CITIZEN_DB)

    if SUPABASE_URL and SUPABASE_KEY and SUPABASE_URL.startswith("http"):
        try:
            headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{SUPABASE_URL}/rest/v1/citizen_recommendations?select=*", headers=headers)
                if res.status_code == 200:
                    supa_citizens = res.json()
                    if supa_citizens and isinstance(supa_citizens, list):
                        citizen_list = supa_citizens
        except Exception as e:
            logger.warning(f"Supabase initial-data fetch fallback: {e}")

    return {
        "status": "success",
        "heritages": OFFICIAL_HERITAGES,
        "citizen_recommendations": citizen_list
    }

@app.post("/api/v1/rag/recommend-heritages")
async def recommend_heritages(req: RAGQueryRequest):
    """
    RAG-based AI heritage recommendation engine with Haversine Nearest-Neighbor TSP optimization.
    Filters top 5 heritages based on prompt/category, calculates optimal order and route coordinates.
    """
    prompt = req.prompt.strip()
    category = req.category_filter
    start_coord = {"lat": req.user_lat or 36.50, "lng": req.user_lng or 127.26}

    # Filter by category if specified
    candidates = list(OFFICIAL_HERITAGES)
    if category and category != "전체":
        candidates = [h for h in candidates if category in h["category"] or any(category in t for t in h["tags"])]
        if not candidates: # fallback if filter too strict
            candidates = list(OFFICIAL_HERITAGES)

    selected_5 = []

    # Attempt OpenAI GPT-4o recommendation if API key is provided
    if OPENAI_API_KEY and prompt:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
                llm_prompt = f"""
                사용자 요청: "{prompt}"
                다음 문화유산 목록 중 가장 적합한 5개를 고르고 이유를 요약하세요.
                목록: {[h['name'] for h in candidates]}
                """
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "너는 대한민국 국가유산 및 세종시 문화유산 전문 여행 가이드 에이전트이다."},
                        {"role": "user", "content": llm_prompt}
                    ],
                    "max_tokens": 300
                }
                res = await client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
                if res.status_code == 200:
                    ai_text = res.json()["choices"][0]["message"]["content"]
                    # Select candidates matching mentions
                    matched = [h for h in candidates if h["name"] in ai_text]
                    if len(matched) >= 3:
                        selected_5 = matched[:5]
        except Exception as e:
            logger.warning(f"OpenAI LLM recommendation fallback trigger: {e}")

    # Fallback heuristic: Rank by keyword relevance & proximity
    if len(selected_5) < 5:
        # Score candidates based on prompt word matches
        prompt_words = prompt.lower().split()
        def score_item(h):
            s = 0
            for w in prompt_words:
                if w in h["name"].lower() or w in h["description"].lower() or any(w in t.lower() for t in h["tags"]):
                    s += 3
            # Give slight preference to proximity
            dist = haversine_distance(start_coord["lat"], start_coord["lng"], h["lat"], h["lng"])
            return s - (dist * 0.05)

        sorted_candidates = sorted(candidates, key=score_item, reverse=True)
        selected_5 = sorted_candidates[:5]

    # Run TSP (Nearest Neighbor) Optimization
    tsp_result = solve_tsp_nearest_neighbor(start_coord, selected_5)

    ai_narrative = (
        f"AI 탐색 결과 '{prompt or '세종 및 주변 백제문화유산 탐방'}'에 부합하는 상위 5개 맞춤 코스를 엄선하였습니다. "
        f"최단 이동 경로(TSP)를 적용하여 총 이동 거리 {tsp_result['total_distance_km']}km로 효율적으로 구성되었습니다."
    )

    return {
        "status": "success",
        "prompt": prompt,
        "recommendations": tsp_result["ordered_items"],
        "total_distance_km": tsp_result["total_distance_km"],
        "route_coordinates": tsp_result["route_coords"],
        "ai_narrative": ai_narrative
    }

@app.post("/api/v1/db/citizen-recommendation")
async def post_citizen_recommendation(input_data: CitizenRecommendationInput):
    """
    Submits a citizen recommendation.
    Enforces dual-field fallback mapping (`reason`/`description`, `photo_url`/`image_url`, `submitted_by`/`user_id`),
    performs Nominatim geocoding if lat/lng are missing, and handles Supabase PGRST204 Auto-Pruning.
    """
    # 1. Dual Field Compensation & Normalization
    final_title = input_data.title.strip()
    final_address = input_data.address.strip()
    final_reason = (input_data.reason or input_data.description or "시민이 직접 추천한 가치 있는 문화유산 장소입니다.").strip()
    final_photo = (input_data.photo_url or input_data.image_url or "").strip()
    final_submitter = (input_data.submitted_by or input_data.user_id or "시민탐방대원").strip()

    # 2. Nominatim Geocoding if coordinates are missing
    lat = input_data.lat
    lng = input_data.lng
    if lat is None or lng is None or lat == 0.0 or lng == 0.0:
        geo = await geocode_with_nominatim(final_address)
        lat = geo["lat"]
        lng = geo["lng"]

    # Build standard payload
    payload = {
        "title": final_title,
        "address": final_address,
        "reason": final_reason,
        "description": final_reason, # Include dual field for schema tolerance
        "photo_url": final_photo,
        "image_url": final_photo,   # Include dual field for schema tolerance
        "submitted_by": final_submitter,
        "user_id": final_submitter,
        "lat": lat,
        "lng": lng
    }

    # 3. Post to Supabase with Auto-Pruning Engine
    result = await post_to_supabase_with_auto_prune("citizen_recommendations", payload)

    # 4. Update Memory Fallback DB
    mem_entry = {
        "id": len(MEMORY_CITIZEN_DB) + 101,
        "title": final_title,
        "address": final_address,
        "reason": final_reason,
        "photo_url": final_photo,
        "submitted_by": final_submitter,
        "lat": lat,
        "lng": lng
    }
    MEMORY_CITIZEN_DB.insert(0, mem_entry)

    return {
        "status": "success",
        "message": "시민 제보 문화유산이 성공적으로 등록되었습니다.",
        "record": mem_entry,
        "supabase_result": result
    }

@app.post("/api/v1/db/user-courses")
async def save_user_course(course: UserCourseInput):
    """Saves a user custom course to Supabase with Auto-Pruning or memory fallback."""
    payload = {
        "course_name": course.course_name,
        "heritage_ids": course.heritage_ids,
        "user_id": course.user_id,
        "total_distance_km": course.total_distance_km
    }

    result = await post_to_supabase_with_auto_prune("courses", payload)

    mem_item = dict(payload)
    mem_item["id"] = len(MEMORY_USER_COURSES) + 1
    MEMORY_USER_COURSES.insert(0, mem_item)

    return {
        "status": "success",
        "message": f"'{course.course_name}' 코스가 보관함에 저장되었습니다.",
        "course": mem_item,
        "supabase_result": result
    }

@app.get("/api/v1/db/user-courses")
async def get_user_courses(user_id: str = Query("guest_user")):
    """Fetches user courses from Supabase or memory store."""
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{SUPABASE_URL}/rest/v1/courses?user_id=eq.{user_id}&select=*", headers=headers)
                if res.status_code == 200:
                    return {"status": "success", "courses": res.json()}
        except Exception as e:
            logger.warning(f"Supabase fetch courses failed: {e}")

    filtered = [c for c in MEMORY_USER_COURSES if c.get("user_id") == user_id or user_id == "guest_user"]
    return {"status": "success", "courses": filtered}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
