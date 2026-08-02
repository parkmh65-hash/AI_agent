"""
app/routers/courses.py
사용자 정의 여행 코스 저장 및 조회 API
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

router = APIRouter(prefix="/api/courses", tags=["courses"])

# In-Memory User Courses Database (DB Dynamic Sync)
COURSES_DB = []

class CourseCreateRequest(BaseModel):
    user_id: str = "user-101"
    title: str
    transport_mode: str = "대중교통"
    total_time: str = "약 1시간 40분"
    items: List[Dict[str, Any]]
    ai_content: Optional[str] = None

@router.post("")
def create_course(req: CourseCreateRequest):
    """여행 코스 저장"""
    new_id = f"course-{len(COURSES_DB) + 1}"
    new_course = {
        "id": new_id,
        "user_id": req.user_id,
        "title": req.title,
        "transport_mode": req.transport_mode,
        "total_time": req.total_time,
        "created_at": datetime.now().isoformat(),
        "items": req.items,
        "ai_content": req.ai_content or "세종 문화유산 AI 코스가 성공적으로 생성되었습니다."
    }
    COURSES_DB.append(new_course)
    return {
        "message": "코스가 성공적으로 저장되었습니다.",
        "course": new_course
    }

@router.get("/{user_id}")
def get_user_courses(user_id: str):
    """특정 사용자가 만든 코스 목록 조회"""
    return [c for c in COURSES_DB if c["user_id"] == user_id]
