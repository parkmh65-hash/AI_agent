"""
app/routers/agentic_rag.py
Agentic RAG 정보검색 시스템 API 엔드포인트
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from app.config import settings
from app.services.agentic_rag_service import run_agentic_rag, run_travel_plan, get_mermaid_graph_definition

router = APIRouter(tags=["agentic-rag"])

class AgenticRAGRequest(BaseModel):
    query: str
    model: Optional[str] = "gpt-4o"
    toggles: Optional[List[str]] = []
    selected_items: Optional[List[str]] = ["기본 정보"]
    selected_model: Optional[str] = "gpt-4o"

class TravelPlanRequest(BaseModel):
    query: str
    travel_date: Optional[str] = "2026-08-15"
    start_location: Optional[str] = "세종시청"
    start_time: Optional[str] = "09:00"
    end_time: Optional[str] = "19:00"
    transport_type: Optional[str] = "car"
    travel_type: Optional[str] = "family"
    companions: Optional[List[str]] = ["adult"]
    interests: Optional[List[str]] = ["history"]
    walking_tolerance: Optional[str] = "medium"
    pet_companion: Optional[bool] = False

@router.options("/api/agentic-rag")
@router.options("/api/v1/agentic-rag")
@router.options("/api/v1/travel-plan")
def options_agentic_rag():
    return {"status": "ok"}

@router.post("/api/agentic-rag")
@router.post("/api/v1/agentic-rag")
def process_agentic_rag(req: AgenticRAGRequest):
    """Agentic RAG 질의 처리 (Agent -> Retrieve -> Grade -> Rewrite -> Generate)"""
    selected_model = req.model or req.selected_model or "gpt-4o"
    toggles = req.toggles or req.selected_items or []
    result = run_agentic_rag(
        question=req.query,
        selected_items=toggles,
        selected_model=selected_model
    )
    return result

@router.post("/api/v1/travel-plan")
def process_travel_plan(req: TravelPlanRequest):
    """신규 추가된 멀티 에이전트 지능형 여행일정 및 지도 경로 최적화 API"""
    payload = req.dict()
    result = run_travel_plan(payload)
    return result

@router.get("/api/v1/config")
def get_public_config():
    """프론트엔드용 비민감성 환경 변수 설정 반환 (API Key 노출 최소화)"""
    return {
        "kakao_javascript_key": settings.KAKAO_JAVASCRIPT_KEY,
        "map_provider": settings.MAP_PROVIDER
    }

@router.get("/api/agentic-rag/graph")
@router.get("/api/v1/agentic-rag/graph")
def get_workflow_graph():
    """LangGraph 워크플로 시각화 Mermaid 정의 반환"""
    mermaid = get_mermaid_graph_definition()
    return {"mermaid": mermaid}

