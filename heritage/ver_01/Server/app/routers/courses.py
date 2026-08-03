"""
app/routers/courses.py
사용자 맞춤 탐방 코스 데이터 저장 및 조회 API (Supabase PostgreSQL `courses` & `course_items` 연동)
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.database import get_supabase

router = APIRouter(prefix="/api/courses", tags=["courses"])

# In-Memory User Courses Database Fallback
COURSES_DB = []

class CourseCreateRequest(BaseModel):
    user_id: Optional[str] = "user-101"
    user_email: Optional[str] = None
    title: Optional[str] = None
    course_name: Optional[str] = None
    transport_mode: Optional[str] = "승용차"
    transport: Optional[str] = None
    total_time: Optional[str] = "약 60분"
    total_time_min: Optional[Any] = 60
    duration: Optional[str] = None
    heritage_ids: Optional[List[str]] = None
    items: Optional[List[Dict[str, Any]]] = []
    ai_content: Optional[str] = None

def normalize_course_record(c: Dict[str, Any]) -> Dict[str, Any]:
    c_id = c.get("id") or c.get("course_id") or f"course-{len(COURSES_DB) + 1}"
    c_title = c.get("title") or c.get("course_name") or "세종시 문화유산 여행 코스"
    c_user = c.get("user_id") or c.get("user_email") or "user-101"
    c_transport = c.get("transport_mode") or c.get("transport") or "승용차"
    c_time = str(c.get("duration") or c.get("total_time") or c.get("total_time_min") or c.get("total_duration_min") or "약 60분")
    items = c.get("items") or []
    h_ids = c.get("heritage_ids") or [it.get("id") or it.get("h_id") for it in items if isinstance(it, dict) and (it.get("id") or it.get("h_id"))]

    c["id"] = c_id
    c["course_id"] = c_id
    c["title"] = c_title
    c["course_name"] = c_title
    c["user_id"] = c_user
    c["user_email"] = c_user
    c["transport_mode"] = c_transport
    c["transport"] = c_transport
    c["total_time"] = c_time
    c["total_time_min"] = c_time
    c["total_duration_min"] = c_time
    c["duration"] = c_time
    c["heritage_ids"] = h_ids
    c["items"] = items
    c["created_at"] = c.get("created_at") or datetime.now().isoformat()
    return c

@router.post("")
def create_course(req: CourseCreateRequest):
    """사용자 맞춤 탐방 코스 저장 (Supabase DB `courses` & `course_items` 저장)"""
    title_val = req.title or req.course_name or "세종시 문화유산 여행 코스"
    user_val = req.user_id or req.user_email or "user-101"
    transport_val = req.transport_mode or req.transport or "승용차"
    time_val = str(req.duration or req.total_time or req.total_time_min or "약 60분")
    
    items_list = req.items or []
    heritage_ids = req.heritage_ids or [it.get("id") or it.get("h_id") for it in items_list if isinstance(it, dict) and (it.get("id") or it.get("h_id"))]

    # Try parsing total duration to int if possible
    duration_min = 60
    try:
        if isinstance(req.total_time_min, int):
            duration_min = req.total_time_min
        else:
            digits = "".join(filter(str.isdigit, str(time_val)))
            if digits:
                duration_min = int(digits)
    except Exception:
        pass

    supabase = get_supabase()
    if supabase:
        try:
            raw_course_db = {
                "user_id": user_val,
                "title": title_val,
                "transport_mode": transport_val,
                "total_duration_min": duration_min,
                "created_at": datetime.now().isoformat()
            }
            res = supabase.table("courses").insert(raw_course_db).execute()
            if res.data and len(res.data) > 0:
                inserted_course = res.data[0]
                course_uuid = inserted_course.get("id")

                # Insert items into course_items table
                course_items_to_insert = []
                for idx, it in enumerate(items_list):
                    h_id_val = it.get("id") if isinstance(it, dict) else str(it)
                    if h_id_val:
                        course_items_to_insert.append({
                            "course_id": course_uuid,
                            "heritage_id": h_id_val,
                            "order_index": idx + 1,
                            "sort_order": idx + 1
                        })

                if course_items_to_insert:
                    try:
                        supabase.table("course_items").insert(course_items_to_insert).execute()
                    except Exception as ie:
                        print(f"course_items insert warning: {ie}")

                full_course = normalize_course_record({
                    "id": course_uuid,
                    "title": title_val,
                    "transport_mode": transport_val,
                    "total_time": f"약 {duration_min}분",
                    "created_at": inserted_course.get("created_at"),
                    "heritage_ids": heritage_ids,
                    "items": items_list
                })
                COURSES_DB.append(full_course)
                return {
                    "message": "코스가 Supabase DB(courses & course_items)에 성공적으로 저장되었습니다.",
                    "course": full_course
                }
        except Exception as e:
            print(f"Supabase courses insert warning: {e}")

    # Fallback to Memory
    new_id = f"course-{len(COURSES_DB) + 1}"
    raw_course = {
        "id": new_id,
        "course_id": new_id,
        "user_id": user_val,
        "title": title_val,
        "transport_mode": transport_val,
        "total_time": time_val,
        "heritage_ids": heritage_ids,
        "items": items_list,
        "created_at": datetime.now().isoformat()
    }
    new_course = normalize_course_record(raw_course)
    COURSES_DB.append(new_course)
    return {
        "message": "코스가 성공적으로 저장되었습니다.",
        "course": new_course
    }

@router.get("", response_model=List[Dict[str, Any]])
@router.get("/{user_id}", response_model=List[Dict[str, Any]])
def get_user_courses(user_id: Optional[str] = None):
    """코스 목록 조회 (Supabase DB `courses` 연동)"""
    supabase = get_supabase()
    if supabase:
        try:
            res = supabase.table("courses").select("*, items:course_items(*)").execute()
            if res.data is not None and len(res.data) > 0:
                courses_res = []
                for row in res.data:
                    c_norm = normalize_course_record(row)
                    courses_res.append(c_norm)
                if user_id:
                    filtered = [c for c in courses_res if c.get("user_id") == user_id or user_id in ["all", "user-101"]]
                    if filtered:
                        return filtered
                return courses_res
        except Exception as e:
            print(f"Supabase courses fetch warning: {e}")

    courses = [normalize_course_record(c) for c in COURSES_DB]
    if user_id and user_id not in ["all", "user-101"]:
        courses = [c for c in courses if c.get("user_id") == user_id]
    return courses
