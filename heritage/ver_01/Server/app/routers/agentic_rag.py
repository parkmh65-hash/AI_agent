"""
app/routers/agentic_rag.py
Agentic RAG 정보검색 시스템 API 엔드포인트
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from app.services.agentic_rag_service import run_agentic_rag, get_mermaid_graph_definition

router = APIRouter(tags=["agentic-rag"])

class AgenticRAGRequest(BaseModel):
    query: str
    model: Optional[str] = "gpt-4o"
    toggles: Optional[List[str]] = []
    selected_items: Optional[List[str]] = ["기본 정보"]
    selected_model: Optional[str] = "gpt-4o"

@router.options("/api/agentic-rag")
@router.options("/api/v1/agentic-rag")
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

@router.get("/api/agentic-rag/graph")
@router.get("/api/v1/agentic-rag/graph")
def get_workflow_graph():
    """LangGraph 워크플로 시각화 Mermaid 정의 반환"""
    mermaid = get_mermaid_graph_definition()
    return {"mermaid": mermaid}
