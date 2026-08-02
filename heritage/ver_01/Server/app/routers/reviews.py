"""
app/routers/reviews.py
코스 탐방 후기 및 평점 데이터 적재, 조회 및 코스별/유산별 평균 만족도 통계 API
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.database import get_supabase

router = APIRouter(prefix="/api/reviews", tags=["reviews"])

# In-Memory Reviews Fallback Store
REVIEWS_DB = [
    {
        "id": "rev-101",
        "review_id": "rev-101",
        "course_id": "course-1",
        "heritage_id": "H1",
        "user_id": "user-101",
        "rating": 5,
        "companion": "가족",
        "companion_type": "가족",
        "transport": "승용차",
        "content": "세종시 유산 코스를 탐방하며 아이들과 함께 비암사와 연기아문의 역사적 의미를 되새길 수 있어 매우 만족스러웠습니다.",
        "text": "세종시 유산 코스를 탐방하며 아이들과 함께 비암사와 연기아문의 역사적 의미를 되새길 수 있어 매우 만족스러웠습니다.",
        "review_text": "세종시 유산 코스를 탐방하며 아이들과 함께 비암사와 연기아문의 역사적 의미를 되새길 수 있어 매우 만족스러웠습니다.",
        "is_public": True,
        "public_yn": "Y",
        "created_at": datetime.now().isoformat()
    }
]

class ReviewCreateRequest(BaseModel):
    course_id: Optional[str] = "course-1"
    heritage_id: Optional[str] = None
    user_id: Optional[str] = "user-101"
    rating: int = 5
    companion: Optional[str] = "가족"
    companion_type: Optional[str] = None
    transport: Optional[str] = "승용차"
    text: Optional[str] = None
    content: Optional[str] = None
    review_text: Optional[str] = None
    is_public: Optional[bool] = True
    public_yn: Optional[str] = "Y"
    photo_url: Optional[str] = None

def normalize_review_record(r: Dict[str, Any]) -> Dict[str, Any]:
    text_val = r.get("text") or r.get("content") or r.get("review_text") or "세종시 문화유산 탐방 후기"
    companion_val = r.get("companion") or r.get("companion_type") or "가족"
    public_val = r.get("is_public") if r.get("is_public") is not None else (r.get("public_yn") == "Y")

    r["id"] = r.get("id") or r.get("review_id") or f"rev-{len(REVIEWS_DB) + 1}"
    r["review_id"] = r["id"]
    r["text"] = text_val
    r["content"] = text_val
    r["review_text"] = text_val
    r["companion"] = companion_val
    r["companion_type"] = companion_val
    r["rating"] = int(r.get("rating") or 5)
    r["is_public"] = public_val
    r["public_yn"] = "Y" if public_val else "N"
    r["created_at"] = r.get("created_at") or datetime.now().isoformat()
    return r

@router.post("")
@router.post("/submit")
def create_review(req: ReviewCreateRequest):
    """후기 및 평점 등록 (Supabase DB `reviews` 테이블 저장)"""
    text_val = req.text or req.content or req.review_text or "문화유산 탐방 후기"
    companion_val = req.companion or req.companion_type or "가족"
    is_pub = req.is_public if req.is_public is not None else (req.public_yn == "Y")
    
    raw_record = {
        "course_id": req.course_id,
        "heritage_id": req.heritage_id,
        "user_id": req.user_id or "user-101",
        "rating": req.rating,
        "companion_type": companion_val,
        "content": text_val,
        "is_public": is_pub,
        "created_at": datetime.now().isoformat()
    }

    supabase = get_supabase()
    if supabase:
        try:
            res = supabase.table("reviews").insert(raw_record).execute()
            if res.data and len(res.data) > 0:
                inserted = normalize_review_record(res.data[0])
                REVIEWS_DB.append(inserted)
                return {
                    "status": "success",
                    "message": "후기 및 평점이 Supabase DB(reviews)에 성공적으로 적재되었습니다.",
                    "review": inserted
                }
        except Exception as e:
            print(f"Supabase reviews insert warning: {e}")

    new_rev = normalize_review_record({
        "id": f"rev-{len(REVIEWS_DB) + 1}",
        "course_id": req.course_id,
        "heritage_id": req.heritage_id,
        "user_id": req.user_id or "user-101",
        "rating": req.rating,
        "companion": companion_val,
        "content": text_val,
        "transport": req.transport,
        "is_public": is_pub,
        "created_at": datetime.now().isoformat()
    })
    REVIEWS_DB.append(new_rev)
    return {
        "status": "success",
        "message": "후기 및 평점이 성공적으로 등록되었습니다.",
        "review": new_rev
    }

@router.get("", response_model=List[Dict[str, Any]])
def get_reviews(
    course_id: Optional[str] = Query(None, description="특정 코스 ID 필터"),
    heritage_id: Optional[str] = Query(None, description="특정 문화유산 ID 필터"),
    limit: Optional[int] = Query(20, description="최신 후기 조회 수")
):
    """전체 후기 목록 또는 특정 코스/유산별 후기 조회"""
    supabase = get_supabase()
    if supabase:
        try:
            query = supabase.table("reviews").select("*").order("created_at", desc=True)
            if course_id:
                query = query.eq("course_id", course_id)
            if heritage_id:
                query = query.eq("heritage_id", heritage_id)
            if limit:
                query = query.limit(limit)
            res = query.execute()
            if res.data is not None and len(res.data) > 0:
                return [normalize_review_record(r) for r in res.data]
        except Exception as e:
            print(f"Supabase reviews fetch warning: {e}")

    records = [normalize_review_record(r) for r in REVIEWS_DB]
    if course_id:
        records = [r for r in records if r.get("course_id") == course_id]
    if heritage_id:
        records = [r for r in records if r.get("heritage_id") == heritage_id]
    if limit:
        records = records[:limit]
    return records

@router.get("/stats")
def get_reviews_stats(course_id: Optional[str] = Query(None, description="특정 코스 ID")):
    """평점/후기 통계 및 코스별 평균 만족도 계산"""
    reviews_list = get_reviews(course_id=course_id, limit=500)
    
    total_reviews = len(reviews_list)
    if total_reviews == 0:
        return {
            "total_reviews": 0,
            "avg_rating": 5.0,
            "rating_counts": {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
        }

    rating_sum = sum(int(r.get("rating") or 5) for r in reviews_list)
    avg_rating = round(rating_sum / total_reviews, 1)

    rating_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    for r in reviews_list:
        score = int(r.get("rating") or 5)
        if score in rating_counts:
            rating_counts[score] += 1

    return {
        "total_reviews": total_reviews,
        "avg_rating": avg_rating,
        "rating_counts": rating_counts,
        "course_id": course_id
    }
