"""
app/routers/ai.py
AI 기능 엔드포인트 (RAG 자연어 맞춤 검색, 생각할거리 생성, Neo4j 연관 코스 추천, 잡지/동화 콘텐츠 생성)
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.services.rag_service import search_heritages_rag
from app.services.graph_service import recommend_course_graph
from app.services.ai_service import generate_think_prompt, generate_course_content

router = APIRouter(prefix="/api/ai", tags=["ai"])

class AISearchRequest(BaseModel):
    query: str
    theme: Optional[str] = None
    top_k: int = 4

class ThinkPromptRequest(BaseModel):
    name: str
    era: str
    description: str

class CourseRecommendRequest(BaseModel):
    start_heritage_id: str
    max_items: int = 3

class CourseContentRequest(BaseModel):
    title: str
    items: List[Dict[str, Any]]
    style: str = "잡지" # 잡지 / 동화 / 역사탐방

@router.post("/search")
def ai_search_heritages(req: AISearchRequest):
    """AI 맞춤 검색 (자연어 질의 -> RAG 추천 리스트)"""
    results = search_heritages_rag(req.query, theme=req.theme, top_k=req.top_k)
    return {
        "query": req.query,
        "theme": req.theme,
        "recommendations": results
    }

@router.post("/think-prompt")
def ai_generate_think_prompt(req: ThinkPromptRequest):
    """문화유산 설명 기반 '생각할 거리' AI 자동 생성"""
    thought = generate_think_prompt(req.name, req.era, req.description)
    return {"think_about": thought}

@router.post("/course-recommend")
def ai_recommend_course(req: CourseRecommendRequest):
    """Neo4j 그래프 관계 기반 코스 추천 (거리, 시대, 테마 연관분석)"""
    recommended_items = recommend_course_graph(req.start_heritage_id, req.max_items)
    return {
        "start_heritage_id": req.start_heritage_id,
        "course_items": recommended_items
    }

@router.post("/course-content")
def ai_generate_course_content(req: CourseContentRequest):
    """코스 저장 시 잡지/동화/역사탐방 스타일 콘텐츠 자동 생성"""
    content = generate_course_content(req.title, req.items, style=req.style)
    return {
        "title": req.title,
        "style": req.style,
        "content": content
    }
