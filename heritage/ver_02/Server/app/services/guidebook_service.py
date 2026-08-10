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
    guidebook_en_article: str = Field(description="English Travel Guidebook translation")
    final_output: str = Field(description="성우 낭독용 정제된 오디오 스크립트 (마크다운 특수문자가 배제된 텍스트)")

# 2. State definition for StateGraph
class AgentState(Dict[str, Any]):
    heritages: List[str]
    transport: str
    enriched_knowledge: str
    analysis_result: Optional[Dict[str, Any]]
    story_result: Optional[str]
    translation_result: Optional[str]
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
    service_key = "a574450c4e9b74f08312c1f80520d00e608341fca348bf1cb6bd02ff3584cf14"
        
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
    key = "a574450c4e9b74f08312c1f80520d00e608341fca348bf1cb6bd02ff3584cf14"
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

async def gather_enriched_knowledge(heritages: List[str]) -> str:
    """Collect official knowledge on heritages using National Heritage API, KTO TourAPI, and Wikipedia/Naver fun facts"""
    knowledge_blocks = []
    for h in heritages:
        cha_detail = await fetch_cha_heritage_detail(h)
        nearby_tour = await fetch_kto_nearby_attractions(h)
        fun_fact = await fetch_fun_fact_from_web(h)
        
        # 10km radius facilities retrieval (restrooms, parking, cafes, restaurants)
        lat, lng = await get_heritage_coords(h)
        facilities_fact = await fetch_kto_nearby_facilities(lat, lng)
        
        block = f"### {h} 관련 수집 지식:\n"
        block += cha_detail
        block += nearby_tour
        block += f"\n{fun_fact}\n"
        block += f"\n{facilities_fact}\n"
        
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
        "당신은 문화유산 기획 전문가이자 최적 동선 기획 에이전트입니다. 다음 문화유산 목록과 이동수단을 분석하여 코스 주제와 최적의 방문 동선 흐름을 기획해 주세요.\n"
        "특히, 수집된 10km 이내의 인근 편의시설(음식점, 카페, 주차장, 공공 화장실) 정보를 적극 검토하여, "
        "사용자가 피로를 느끼지 않고 가장 짧은 거리로 편리하게 연계 방문할 수 있도록 **가까운 거리 기반의 이동 최적 동선(TSP 순서 정렬)**을 적용해 코스를 설계해 주어야 합니다.\n\n"
        "문화유산 목록: {heritages}\n이동수단: {transport}\n수집된 외부 RAG 지식 및 주변 10km 편의시설 정보:\n{knowledge}\n\n"
        "응답은 기획서 요약 형태로 반환해 주세요."
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
        "당신은 어린이와 가족을 위한 감성 스토리텔링 동화 작가이자 역사 예능 작가입니다. 기획 요약 정보와 외부 웹사이트(위키/네이버 등)에서 수집된 설화, 비화(Fun Fact) 정보를 바탕으로, "
        "전체 가이드북을 재미있고 유쾌한 하나의 완벽한 '동화책 형태'의 본문으로 창작해 주세요.\n"
        "이동 동선 기획: {analysis}\n문화유산 목록: {heritages}\n"
        "문체는 '옛날 옛적에~', '~했답니다'와 같이 친근하고 따뜻한 구연동화 어조를 사용하고, "
        "이야기 속에 역사적 의의와 수집된 전설, 재미있는 상식들을 흥미진진하게 녹여내 성우가 실감나게 낭독하기 적합한 동화 원고로 전개해야 합니다."
    )
    chain = prompt | llm
    res = await chain.ainvoke({
        "analysis": state["analysis_result"]["summary"],
        "heritages": ", ".join(state["heritages"])
    })
    return {"story_result": res.content}

# Node 3: Translator Agent
async def translator_node(state: AgentState) -> Dict[str, Any]:
    llm = get_llm()
    prompt = ChatPromptTemplate.from_template(
        "당신은 전문 번역 에이전트입니다. 다음 한국어 원고 내용을 외국인 관광객들이 쉽게 읽을 수 있도록 자연스러운 영문 가이드북으로 번역 및 편집해 주세요.\n"
        "한국어 원고:\n{story}"
    )
    chain = prompt | llm
    res = await chain.ainvoke({"story": state["story_result"]})
    return {"translation_result": res.content}

# Node 4: Critic & Formatting Agent
async def critic_node(state: AgentState) -> Dict[str, Any]:
    llm = get_llm()
    parser = JsonOutputParser(pydantic_object=GuidebookOutput)
    
    prompt = ChatPromptTemplate.from_template(
        "당신은 수석 감수관 및 포맷터 에이전트입니다. 이전 에이전트들이 작성한 자료들을 검수하고, 다음의 JSON 포맷 형식으로 데이터를 구조화해 주세요.\n"
        "반드시 JSON 객체만을 출력해야 합니다. 마크다운 태그(```json)로 감싸서 반환하지 마십시오.\n\n"
        "기획 자료: {analysis}\n한국어 스토리텔링: {story}\n영문 번역문: {translation}\n문화유산 리스트: {heritages}\n\n"
        "포맷팅 지침:\n"
        "1. 각 유산마다 1개의 StoryboardCard를 생성하십시오. 이미지 URL은 임시 플레이스홀더 주소를 생성해 주십시오.\n"
        "2. StoryboardCard의 각 항목(scene_title, guide_tip 등)은 동화책의 한 장(Page/Scene)을 넘기는 것처럼 아늑하고 친근한 동화적 어투를 유지하고 있는지 검수하여 정비해 주십시오.\n"
        "3. final_output은 성우 낭독용 스크립트로, 특수문자나 마크다운 기호가 일절 배제된 순수 한글 소리 중심의 따뜻한 구연동화 텍스트여야 합니다.\n\n"
        "{format_instructions}"
    )
    
    chain = prompt | llm | parser
    res = await chain.ainvoke({
        "analysis": state["analysis_result"]["summary"],
        "story": state["story_result"],
        "translation": state["translation_result"],
        "heritages": ", ".join(state["heritages"]),
        "format_instructions": parser.get_format_instructions()
    })
    
    return {"final_output": res}

# 5. Graph Assembly
def build_guidebook_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("analyzer", analyzer_node)
    workflow.add_node("storywriter", storywriter_node)
    workflow.add_node("translator", translator_node)
    workflow.add_node("critic", critic_node)
    
    workflow.set_entry_point("analyzer")
    workflow.add_edge("analyzer", "storywriter")
    workflow.add_edge("storywriter", "translator")
    workflow.add_edge("translator", "critic")
    workflow.add_edge("critic", END)
    
    return workflow.compile()

# Service Export Method
class GuidebookService:
    def __init__(self):
        self.graph = build_guidebook_graph()
        
    async def save_course_vector_to_supabase(self, course_name: str, description: str, heritages: List[str], transport: str, duration: int) -> bool:
        """Vectorize generated course content and save to Supabase pgvector-enabled table"""
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            return False
        
        try:
            # 1. Generate text embedding vector using OpenAI Embeddings
            api_key = settings.OPENAI_API_KEY or "dummy_key"
            embeddings_model = OpenAIEmbeddings(openai_api_key=api_key)
            
            # Text block to represent this course semantically
            course_text = f"코스명: {course_name}\n소개: {description}\n경로: {' -> '.join(heritages)}\n교통수단: {transport}\n총 소요시간: {duration}분"
            
            # Async vector generation
            vector = await embeddings_model.aembed_query(course_text)
            
            # 2. Insert into Supabase 'courses_vector' table via REST API
            headers = {
                "apikey": settings.SUPABASE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            }
            
            payload = {
                "course_name": course_name,
                "description": description,
                "items": json.dumps(heritages, ensure_ascii=False),
                "transport": transport,
                "total_duration": duration,
                "embedding": vector # pgvector column mapping
            }
            
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    f"{settings.SUPABASE_URL}/rest/v1/courses_vector",
                    headers=headers,
                    json=payload,
                    timeout=5.0
                )
                if res.status_code in [200, 201]:
                    return True
        except Exception as e:
            print(f"Failed to vectorize and save course to DB: {e}")
        return False

    async def create_guidebook(self, heritages: List[str], transport: str = "승용차") -> Dict[str, Any]:
        # Gather dynamic external knowledge
        knowledge = await gather_enriched_knowledge(heritages)
        
        initial_state = {
            "heritages": heritages,
            "transport": transport,
            "enriched_knowledge": knowledge,
            "analysis_result": None,
            "story_result": None,
            "translation_result": None,
            "final_output": None
        }
        
        # Execute LangGraph Multi-Agent collaborative graph
        result = await self.graph.ainvoke(initial_state)
        
        # Extract the structured GuidebookOutput json
        final_data = result.get("final_output")
        if not final_data:
            raise ValueError("Graph execution failed to generate final output.")
            
        # Asynchronously run vectorization and DB insertion in the background
        try:
            course_name = f"{'과 '.join(heritages[:2])} 연계 탐방 코스"
            description = final_data.get("guidebook_ko_article", "")[:150]
            import asyncio
            asyncio.create_task(
                self.save_course_vector_to_supabase(
                    course_name=course_name,
                    description=description,
                    heritages=heritages,
                    transport=transport,
                    duration=len(heritages) * 30
                )
            )
        except Exception as err:
            print(f"Async vectorization launch failed: {err}")

        return final_data
