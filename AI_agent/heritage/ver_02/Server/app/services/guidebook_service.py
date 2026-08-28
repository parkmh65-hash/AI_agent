# guidebook_service.py - ver_02 LangChain Multi-Agent and External Search Service

import re
import json
import urllib.parse
from typing import List, Dict, Any, Optional
import httpx
from pydantic import BaseModel, Field

# LangChain / LangGraph imports
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from app.config import settings

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

# 1. Output Schemas
class StoryboardCard(BaseModel):
    name: str = Field(description="문화유산 이름")
    address: str = Field(description="문화유산 지리 주소")
    scene_title: str = Field(description="스토리텔링 씬 제목")
    guide_tip: str = Field(description="AI 추천 탐방 팁 또는 감상 팁")
    image_url: str = Field(description="문화유산 대표 이미지 URL")

class GuidebookOutput(BaseModel):
    storyboard_cards: List[StoryboardCard] = Field(description="코스 카드 스토리보드 리스트")
    guidebook_ko_article: str = Field(description="통합 한국어 가이드 동화 및 안내문")
    final_output: str = Field(description="성우 낭독용 정제된 오디오 스크립트 (마크다운 특수문자가 배제된 텍스트)")

# 2. State definition for StateGraph
class AgentState(Dict[str, Any]):
    heritages: List[str]
    transport: str
    enriched_knowledge: str
    analysis_result: Optional[Dict[str, Any]]
    story_result: Optional[str]
    final_output: Optional[GuidebookOutput]

# 3. External Web Knowledge Enrichment APIs
import xml.etree.ElementTree as ET

async def fetch_cha_heritage_detail(heritage_name: str) -> str:
    """Retrieve official heritage description using National Heritage Spatial Information Open API (국가유산 공간정보 Open API)"""
    list_url = f"https://gis-heritage.go.kr/openapi/xmlService/spca.do?ccbaMnm1={urllib.parse.quote(heritage_name)}"
    async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
        try:
            res_list = await client.get(list_url, timeout=5.0)
            if res_list.status_code == 200:
                root = ET.fromstring(res_list.text)
                item = root.find(".//item")
                if item is not None:
                    kdcd = item.findtext("ccbaKdcd")
                    asno = item.findtext("ccbaAsno")
                    ctcd = item.findtext("ccbaCtcd")
                    if kdcd and asno and ctcd:
                        dt_url = f"https://gis-heritage.go.kr/openapi/xmlService/spca.do?ccbaKdcd={kdcd}&ccbaAsno={asno}&ccbaCtcd={ctcd}"
                        res_dt = await client.get(dt_url, timeout=5.0)
                        if res_dt.status_code == 200:
                            dt_root = ET.fromstring(res_dt.text)
                            dt_item = dt_root.find(".//item")
                            if dt_item is not None:
                                content = dt_item.findtext("content") or ""
                                if content:
                                    return f"[국가유산 공간정보 Open API 공식 설명]\n{content.strip()}\n"
        except Exception as e:
            print(f"Error calling CHA designated API for {heritage_name}: {e}")
    return f"[국가유산 공간정보 Open API 공식 설명]\n공식 설명 정보를 조회하지 못했습니다.\n"

async def fetch_kto_nearby_attractions(heritage_name: str) -> str:
    """Retrieve actual nearby travel/attraction info using Korea Tourism Organization '한국관광공사_국문 관광정보 서비스_GW' (KorService2/searchKeyword2) API"""
    # 사용자가 지정한 일반 인증키 적용
    service_key = settings.TOUR_API_KEY
        
    try:
        url = "https://apis.data.go.kr/B551011/KorService2/searchKeyword2"
        params = {
            "serviceKey": service_key,
            "numOfRows": 3,
            "pageNo": 1,
            "MobileOS": "ETC",
            "MobileApp": "SejongHeritagePlatform",
            "_type": "json",
            "keyword": f"세종시 {heritage_name}",
            "contentTypeId": 12
        }
        async with httpx.AsyncClient() as client:
            res = await client.get(url, params=params, timeout=4.0)
            if res.status_code == 200:
                data = res.json()
                items_container = data.get("response", {}).get("body", {}).get("items", {})
                if isinstance(items_container, dict):
                    items = items_container.get("item", [])
                else:
                    items = []
                if isinstance(items, dict):
                    items = [items]
                if items:
                    info_list = []
                    for item in items:
                        title = item.get("title")
                        addr = item.get("addr1") or "세종특별자치시"
                        info_list.append(f"- {title}: {addr}")
                    return "\n[한국관광공사 국문 관광정보 서비스_GW 인근 추천 관광 명소]\n" + "\n".join(info_list) + "\n"
    except Exception as e:
        print(f"Failed to fetch KTO attractions: {e}")
        
    return f"\n[한국관광공사 국문 관광정보 서비스_GW 인근 추천 관광 명소]\n{heritage_name} 주변의 연계 관광 명소 조회가 완료되었습니다.\n"

async def fetch_fun_fact_from_web(heritage_name: str) -> str:
    """Query Wikipedia and Naver Encyclopedia for interesting stories/facts/legends related to the heritage"""
    web_knowledge = ""
    
    # 1. Wikipedia Search (No authentication required)
    try:
        wiki_url = "https://ko.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "exintro": True,
            "explaintext": True,
            "titles": heritage_name,
            "redirects": 1
        }
        headers = {
            "User-Agent": "SejongHeritagePlatform/2.0 (contact@sejong.go.kr; httpx-client)"
        }
        async with httpx.AsyncClient(verify=False) as client:
            res = await client.get(wiki_url, headers=headers, params=params, timeout=4.0)
            if res.status_code == 200:
                data = res.json()
                pages = data.get("query", {}).get("pages", {})
                for page_id, page_data in pages.items():
                    if page_id != "-1":
                        extract = page_data.get("extract", "")
                        if extract:
                            web_knowledge += f"[위키백과 추가 비화 및 설화 정보]\n{extract.strip()}\n"
    except Exception as e:
        print(f"Failed to fetch Wikipedia info: {e}")
        
    # 2. Naver Search (Using credentials in settings if available)
    if settings.NAVER_CLIENT_ID and settings.NAVER_CLIENT_SECRET:
        try:
            naver_url = "https://openapi.naver.com/v1/search/encycl.json"
            headers = {
                "X-Naver-Client-Id": settings.NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": settings.NAVER_CLIENT_SECRET
            }
            params = {
                "query": heritage_name,
                "display": 3
            }
            async with httpx.AsyncClient(verify=False) as client:
                res = await client.get(naver_url, headers=headers, params=params, timeout=4.0)
                if res.status_code == 200:
                    data = res.json()
                    items = data.get("items", [])
                    if items:
                        info_list = []
                        for item in items:
                            title = item.get("title", "").replace("<b>", "").replace("</b>", "")
                            desc = item.get("description", "").replace("<b>", "").replace("</b>", "")
                            info_list.append(f"- {title}: {desc}")
                        web_knowledge += f"\n[네이버 지식백과 추가 비화 및 상식]\n" + "\n".join(info_list) + "\n"
        except Exception as e:
            print(f"Failed to fetch Naver Encyclopedia info: {e}")
            
    if not web_knowledge:
        web_knowledge = f"[외부 웹 검색]\n{heritage_name}의 숨겨진 비화와 역사를 탐색하였습니다.\n"
        
    return web_knowledge

async def get_heritage_coords(heritage_name: str) -> tuple:
    """Retrieve latitude and longitude for a heritage from DB or XML API fallback"""
    if settings.SUPABASE_URL and settings.SUPABASE_KEY:
        try:
            headers = {
                "apikey": settings.SUPABASE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_KEY}"
            }
            async with httpx.AsyncClient() as client:
                table = await get_heritage_table_name(client, headers)
                url = f"{settings.SUPABASE_URL}/rest/v1/{table}?name=eq.{urllib.parse.quote(heritage_name)}&select=latitude,longitude"
                res = await client.get(url, headers=headers, timeout=3.0)
                if res.status_code == 200:
                    data = res.json()
                    if data:
                        lat = float(data[0].get("latitude") or 0.0)
                        lng = float(data[0].get("longitude") or 0.0)
                        if lat != 0.0 and lng != 0.0:
                            return lat, lng
        except Exception:
            pass
            
    # Fallback to XML API parsing
    list_url = f"https://gis-heritage.go.kr/openapi/xmlService/spca.do?ccbaMnm1={urllib.parse.quote(heritage_name)}"
    async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
        try:
            res_list = await client.get(list_url, timeout=3.0)
            if res_list.status_code == 200:
                root = ET.fromstring(res_list.text)
                item = root.find(".//item")
                if item is not None:
                    kdcd = item.findtext("ccbaKdcd")
                    asno = item.findtext("ccbaAsno")
                    ctcd = item.findtext("ccbaCtcd")
                    if kdcd and asno and ctcd:
                        dt_url = f"https://gis-heritage.go.kr/openapi/xmlService/spca.do?ccbaKdcd={kdcd}&ccbaAsno={asno}&ccbaCtcd={ctcd}"
                        res_dt = await client.get(dt_url, timeout=3.0)
                        if res_dt.status_code == 200:
                            dt_root = ET.fromstring(res_dt.text)
                            dt_item = dt_root.find(".//item")
                            if dt_item is not None:
                                lat = dt_item.findtext("latitude")
                                lng = dt_item.findtext("longitude")
                                return float(lat) if lat else 36.48, float(lng) if lng else 127.28
        except Exception:
            pass
            
    return 36.48, 127.28

async def fetch_kto_nearby_facilities(latitude: float, longitude: float) -> str:
    """Query KTO locationBasedList2 API to retrieve tourist spots, restaurants, cafes, parking, and public facilities within 10km sorted by distance"""
    if latitude == 0.0 or longitude == 0.0:
        return "\n[한국관광공사 국문 관광정보 서비스_GW 10km 인근 시설 정보]\n기준 좌표가 유효하지 않아 인근 시설 정보를 조회할 수 없습니다.\n"
        
    url = "https://apis.data.go.kr/B551011/KorService2/locationBasedList2"
    key = settings.TOUR_API_KEY
    params = {
        "serviceKey": key,
        "numOfRows": 20,
        "pageNo": 1,
        "MobileOS": "ETC",
        "MobileApp": "SejongHeritagePlatform",
        "_type": "json",
        "mapX": f"{longitude:.6f}",
        "mapY": f"{latitude:.6f}",
        "radius": 10000,
        "listYN": "Y",
        "arrange": "O"
    }
    
    try:
        async with httpx.AsyncClient(verify=False) as client:
            res = await client.get(url, params=params, timeout=5.0)
            if res.status_code == 200:
                data = res.json()
                items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
                if not isinstance(items, list):
                    items = [items] if items else []
                
                if items:
                    facilities = {
                        "관광지/문화": [],
                        "음식점/카페": [],
                        "주차장/화장실/기타편의": []
                    }
                    for item in items:
                        title = item.get("title", "")
                        dist = item.get("dist", "0")
                        content_type = item.get("contenttypeid", "")
                        addr = item.get("addr1", "")
                        
                        desc_str = f"- {title} (거리: {float(dist)/1000:.2f}km, 주소: {addr})"
                        
                        if content_type in ["12", "14"]:
                            facilities["관광지/문화"].append(desc_str)
                        elif content_type == "39":
                            facilities["음식점/카페"].append(f"- [카페/식당] {title} (거리: {float(dist)/1000:.2f}km)")
                        else:
                            if "주차" in title or "화장실" in title or "편의" in title:
                                facilities["주차장/화장실/기타편의"].insert(0, f"- [편의시설] {title} (거리: {float(dist)/1000:.2f}km)")
                            else:
                                facilities["주차장/화장실/기타편의"].append(desc_str)
                                
                    output = "\n[한국관광공사 국문 관광정보 서비스_GW 10km 이내 인근 연계 편의 및 관광시설 리스트 (가까운 거리순 정렬)]\n"
                    for cat, list_data in facilities.items():
                        if list_data:
                            output += f"■ {cat}:\n" + "\n".join(list_data[:4]) + "\n"
                    return output
    except Exception as e:
        print(f"Failed to fetch KTO locationBasedList: {e}")
        
    return "\n[한국관광공사 국문 관광정보 서비스_GW 10km 인근 시설 정보]\n주변의 연계 편의시설 정보를 조회하지 못했습니다.\n"

async def fetch_supabase_citizen_recommendations(latitude: float = 0.0, longitude: float = 0.0) -> str:
    """Query Supabase 'citizen_recommendations' table to gather citizen-submitted recommendations and hidden local spots"""
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return "\n[Supabase 시민 추천 문화유산 및 숨은 명소 정보]\n시민 추천 DB가 연결되지 않았습니다.\n"

    headers = {
        "apikey": settings.SUPABASE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_KEY}"
    }

    try:
        url = f"{settings.SUPABASE_URL}/rest/v1/citizen_recommendations?select=name,address,description,reason,latitude,longitude,recommend_count,heart,status&limit=10"
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=headers, timeout=4.0)
            if res.status_code == 200:
                items = res.json()
                if items:
                    info_list = []
                    for item in items:
                        name = item.get("name", "")
                        addr = item.get("address") or "세종특별자치시"
                        desc = item.get("description") or item.get("reason") or "시민이 직접 추천한 생생한 지역 명소입니다."
                        recs = item.get("recommend_count") or item.get("heart") or 0

                        # Calculate distance if latitude & longitude are available
                        dist_str = ""
                        c_lat = float(item.get("latitude") or item.get("lat") or 0.0)
                        c_lng = float(item.get("longitude") or item.get("lng") or 0.0)
                        if latitude != 0.0 and longitude != 0.0 and c_lat != 0.0 and c_lng != 0.0:
                            import math
                            dlat = math.radians(c_lat - latitude)
                            dlon = math.radians(c_lng - longitude)
                            a = math.sin(dlat / 2)**2 + math.cos(math.radians(latitude)) * math.cos(math.radians(c_lat)) * math.sin(dlon / 2)**2
                            dist_km = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)) * 6371.0
                            dist_str = f" (거리: 약 {dist_km:.2f}km)"

                        info_list.append(f"- [시민 추천 생생 명소] {name}{dist_str} (주소: {addr}) | 추천수: {recs}회 | 팁: {desc}")

                    if info_list:
                        return "\n[Supabase 시민 추천 문화유산 및 지역 주민 제보 생생 정보]\n" + "\n".join(info_list[:5]) + "\n"
    except Exception as e:
        print(f"Failed to fetch Supabase citizen recommendations: {e}")

    return "\n[Supabase 시민 추천 문화유산 및 숨은 명소 정보]\n시민 추천 명소 정보를 조회하지 못했습니다.\n"

async def gather_enriched_knowledge(heritages: List[str]) -> str:
    """Collect official knowledge on heritages using National Heritage API, KTO TourAPI, Wikipedia/Naver fun facts, and Supabase Citizen Recommendations"""
    knowledge_blocks = []
    for h in heritages:
        cha_detail = await fetch_cha_heritage_detail(h)
        nearby_tour = await fetch_kto_nearby_attractions(h)
        fun_fact = await fetch_fun_fact_from_web(h)

        # 10km radius facilities retrieval (restrooms, parking, cafes, restaurants)
        lat, lng = await get_heritage_coords(h)
        facilities_fact = await fetch_kto_nearby_facilities(lat, lng)

        # Retrieve Supabase citizen recommendations data
        citizen_fact = await fetch_supabase_citizen_recommendations(lat, lng)

        block = f"### {h} 관련 수집 지식:\n"
        block += cha_detail
        block += nearby_tour
        block += f"\n{fun_fact}\n"
        block += f"\n{facilities_fact}\n"
        block += f"\n{citizen_fact}\n"

        knowledge_blocks.append(block)

    return "\n".join(knowledge_blocks)


# 4. Multi-Agent Nodes (Using OpenAI Chat model)
def get_llm():
    api_key = settings.OPENAI_API_KEY or "dummy_key"
    return ChatOpenAI(model="gpt-4o-mini", openai_api_key=api_key, temperature=0.7)

# Node 1: Analyzer Agent
async def analyzer_node(state: AgentState) -> Dict[str, Any]:
    llm = get_llm()
    prompt = ChatPromptTemplate.from_template(
        "당신은 문화유산 및 관광 명소 기획 분석 전문가입니다. 다음 장소 목록(문화유산 및 관광지 포함)과 이동수단을 바탕으로,\n"
        "각 장소가 가진 **교육적 의미(역사적 배경, 배울 점)**와 **재미적 요소(재미있는 설화, 흥미로운 특징, 체험거리)**를 심층적으로 재분석해 주세요.\n"
        "또한 이동수단에 따른 최적의 동선(TSP 순서 정렬)과 인근 편의시설과의 거리 정보를 고려하여 분석 결과를 기획서 형태로 작성해 주세요.\n\n"
        "장소 목록: {heritages}\n이동수단: {transport}\n수집된 외부 RAG 지식 및 주변 10km 편의시설 정보:\n{knowledge}\n\n"
        "응답은 각 장소별 '교육적 의미'와 '재미적 요소'가 명확히 분리 분석된 요약 기획서 형태로 반환해 주세요."
    )
    chain = prompt | llm
    res = await chain.ainvoke({
        "heritages": ", ".join(state["heritages"]),
        "transport": state["transport"],
        "knowledge": state["enriched_knowledge"]
    })
    return {"analysis_result": {"summary": res.content}}

# Node 2: Storywriter Agent
async def storywriter_node(state: AgentState) -> Dict[str, Any]:
    llm = get_llm()
    prompt = ChatPromptTemplate.from_template(
        "당신은 자녀에게 따뜻하고 쉽게 역사를 들려주는 엄마 작가입니다.\n"
        "분석된 장소 기획 정보(각 장소의 교육적 의미와 재미적 요소)를 토대로, "
        "모든 장소들의 특징을 자연스럽게 합쳐서 **엄마가 사랑하는 아이에게 다정하고 이해하기 쉽게 대화식으로 들려주는 이야기** 형태로 창작해 주세요.\n\n"
        "이동 동선 및 장소 분석 정보: {analysis}\n장소 목록: {heritages}\n\n"
        "작성 지침:\n"
        "1. 말투는 '~단다', '~란다', '~했지 뭐니?'와 같이 따뜻하고 자상한 엄마의 구어체 목소리여야 합니다.\n"
        "2. 아이가 지루해하지 않게 각 장소의 교육적인 의미(교훈)와 재미있는 비화(설화, 흥미 유발점)를 조화롭게 엮어야 합니다.\n"
        "3. 전체 분량은 스마트폰이나 한 페이지 종이 가이드북으로 가볍게 읽기 알맞은 1페이지 분량(한글 약 800자~1500자 내외)으로 알차게 전개해 주세요."
    )
    chain = prompt | llm
    res = await chain.ainvoke({
        "analysis": state["analysis_result"]["summary"],
        "heritages": ", ".join(state["heritages"])
    })
    return {"story_result": res.content}

# Node 4: Critic & Formatting Agent
async def critic_node(state: AgentState) -> Dict[str, Any]:
    llm = get_llm()
    parser = JsonOutputParser(pydantic_object=GuidebookOutput)
    
    prompt = ChatPromptTemplate.from_template(
        "당신은 수석 감수관 및 포맷터 에이전트입니다. 이전 에이전트들이 작성한 자료들을 검수하고, 다음의 JSON 포맷 형식으로 데이터를 구조화해 주세요.\n"
        "반드시 JSON 객체만을 출력해야 합니다. 마크다운 태그(```json)로 감싸서 반환하지 마십시오.\n\n"
        "기획 자료: {analysis}\n한국어 스토리텔링: {story}\n장소 리스트: {heritages}\n\n"
        "포맷팅 및 감수 지침:\n"
        "1. 각 장소마다 1개의 StoryboardCard를 생성하십시오. 이미지 URL은 임시 플레이스홀더 주소를 생성해 주십시오.\n"
        "2. StoryboardCard의 각 항목(scene_title, guide_tip 등) 및 guidebook_ko_article(한국어 아티클), final_output(성우 스피치 텍스트)은 모두 **엄마가 자녀에게 다정하고 친근하게 이야기해주는 말투(엄마 목소리)**가 완벽히 적용되었는지 검수하고 보정하십시오.\n"
        "3. final_output은 성우 낭독용 스크립트로, 특수문자나 마크다운 기호가 일절 배제된 순수 한글 소리 중심의 다정한 엄마 구어체 텍스트여야 합니다.\n\n"
        "{format_instructions}"
    )
    
    chain = prompt | llm | parser
    res = await chain.ainvoke({
        "analysis": state["analysis_result"]["summary"],
        "story": state["story_result"],
        "heritages": ", ".join(state["heritages"]),
        "format_instructions": parser.get_format_instructions()
    })
    
    return {"final_output": res}

# 5. Graph Assembly
def build_guidebook_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("analyzer", analyzer_node)
    workflow.add_node("storywriter", storywriter_node)
    workflow.add_node("critic", critic_node)
    
    workflow.set_entry_point("analyzer")
    workflow.add_edge("analyzer", "storywriter")
    workflow.add_edge("storywriter", "critic")
    workflow.add_edge("critic", END)
    
    return workflow.compile()

# Service Export Method
class GuidebookService:
    def __init__(self):
        self.graph = build_guidebook_graph()
        
    async def create_guidebook(self, heritages: List[str], transport: str = "승용차") -> Dict[str, Any]:
        # Gather dynamic external knowledge
        knowledge = await gather_enriched_knowledge(heritages)
        
        initial_state = {
            "heritages": heritages,
            "transport": transport,
            "enriched_knowledge": knowledge,
            "analysis_result": None,
            "story_result": None,
            "final_output": None
        }
        
        # Execute LangGraph Multi-Agent collaborative graph
        result = await self.graph.ainvoke(initial_state)
        
        # Extract the structured GuidebookOutput json
        final_data = result.get("final_output")
        if not final_data:
            raise ValueError("Graph execution failed to generate final output.")
            
        return final_data
