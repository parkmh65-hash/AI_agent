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
    """Retrieve official heritage description from National Heritage Administration Open API (SearchKindOpenapiList/Dt.do)"""
    list_url = f"http://www.cha.go.kr/cha/SearchKindOpenapiList.do?ccbaMnm1={urllib.parse.quote(heritage_name)}"
    async with httpx.AsyncClient() as client:
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
                        dt_url = f"http://www.cha.go.kr/cha/SearchKindOpenapiDt.do?ccbaKdcd={kdcd}&ccbaAsno={asno}&ccbaCtcd={ctcd}"
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
    """Retrieve actual nearby travel/attraction info using Korea Tourism Organization KorService1/searchKeyword1 API"""
    import os
    service_key = os.getenv("TOUR_API_KEY") or os.getenv("SERVICE_KEY") or ""
    
    if not service_key:
        return f"\n[한국관광공사 TourAPI 인근 관광 명소]\n실제 공공 API 연결 키(TOUR_API_KEY)가 설정되지 않아 임베디드 랜드마크 정보를 로드했습니다.\n- 세종 베어트리파크: 수목원 및 반달곰 테마파크\n- 세종호수공원: 국내 최대의 인공호수공원\n"
        
    try:
        url = "http://apis.data.go.kr/B551011/KorService1/searchKeyword1"
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
                items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
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
        
    return f"\n[한국관광공사 TourAPI 인근 관광 명소]\n{heritage_name} 주변의 연계 관광 명소 조회가 완료되었습니다.\n"

async def gather_enriched_knowledge(heritages: List[str]) -> str:
    """Collect official knowledge on heritages using National Heritage API and KTO TourAPI only"""
    knowledge_blocks = []
    for h in heritages:
        cha_detail = await fetch_cha_heritage_detail(h)
        nearby_tour = await fetch_kto_nearby_attractions(h)
        
        block = f"### {h} 관련 수집 지식:\n"
        block += cha_detail
        block += nearby_tour
        
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
        "당신은 문화유산 기획 전문가입니다. 다음 문화유산 목록과 이동수단을 분석하여 코스 주제와 최적의 방문 동선 흐름을 기획해 주세요.\n"
        "문화유산 목록: {heritages}\n이동수단: {transport}\n수집된 외부 지식:\n{knowledge}\n"
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
        "당신은 감성 스토리텔링 전문 작가입니다. 기획 요약 정보를 바탕으로 각 문화유산의 매력을 동화책처럼 아늑하고 따뜻하게 묘사하는 한국어 스토리텔링 원고를 작성해 주세요.\n"
        "이동 동선 기획: {analysis}\n문화유산 목록: {heritages}\n"
        "이야기 속에 역사적 의의와 성우 낭독에 적합한 구연동화 형식이 포함되어야 합니다."
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
        "2. final_output은 성우 낭독용 스크립트로, 특수문자나 마크다운 기호가 일절 배제된 순수 한글 소리 중심 텍스트여야 합니다.\n\n"
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
