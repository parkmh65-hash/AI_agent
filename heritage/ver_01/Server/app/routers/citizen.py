"""
app/routers/citizen.py
시민 참여형 문화유산 발굴 제보 및 내 추천 조회 API
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

router = APIRouter(tags=["citizen"])

# In-Memory Citizen Recommendations Store (DB Dynamic Sync)
CITIZEN_RECOMMENDATIONS_DB = []

class CitizenRecommendationSubmit(BaseModel):
    name: str
    image_url: Optional[str] = None
    photo_url: Optional[str] = None
    latitude: Optional[float] = None
    lat: Optional[float] = None
    longitude: Optional[float] = None
    lng: Optional[float] = None
    address: Optional[str] = "세종특별자치시"
    description: Optional[str] = None
    reason: Optional[str] = None
    user_id: Optional[str] = "user_01"
    submitted_by: Optional[str] = "user@sejong.go.kr"

def normalize_citizen_record(r: Dict[str, Any]) -> Dict[str, Any]:
    image_url = r.get("image_url") or r.get("photo_url") or "https://images.unsplash.com/photo-1548013146-72479768bada?w=600&q=80"
    lat_val = float(r.get("latitude") or r.get("lat") or 36.48)
    lng_val = float(r.get("longitude") or r.get("lng") or 127.28)
    desc_val = r.get("description") or r.get("reason") or r.get("report_reason") or "시민 추천 문화유산 제보"
    user_val = r.get("user_id") or r.get("submitted_by") or "user@sejong.go.kr"
    status_val = r.get("status") or "신청중"
    feedback_val = r.get("feedback") or r.get("reviewer_note") or "담당자 확인 대기 중"
    time_val = r.get("submitted_at") or r.get("created_at") or datetime.now().isoformat()

    # 호환성 무결성을 위해 신구 버전 컬럼명을 모두 맵에 반환
    r["photo_url"] = image_url
    r["image_url"] = image_url
    r["lat"] = lat_val
    r["latitude"] = lat_val
    r["lng"] = lng_val
    r["longitude"] = lng_val
    r["reason"] = desc_val
    r["description"] = desc_val
    r["report_reason"] = desc_val
    r["user_id"] = user_val
    r["submitted_by"] = user_val
    r["status"] = status_val
    r["feedback"] = feedback_val
    r["reviewer_note"] = feedback_val
    r["submitted_at"] = time_val
    r["created_at"] = time_val
    return r

@router.post("/api/citizen-recommendations")
def submit_citizen_recommendation(data: CitizenRecommendationSubmit):
    """시민 추천 문화유산 제보 제출 (Supabase DB `citizen_recommendations` 테이블 저장)"""
    img_url = data.image_url or data.photo_url or "https://images.unsplash.com/photo-1548013146-72479768bada?w=600&q=80"
    lat_val = float(data.latitude or data.lat or 36.48)
    lng_val = float(data.longitude or data.lng or 127.28)
    desc_val = data.description or data.reason or "시민 추천 문화유산 제보"
    user_val = data.user_id or data.submitted_by or "user@sejong.go.kr"
    address_val = data.address or "세종특별자치시"

    raw_record = {
        "name": data.name,
        "address": address_val,
        "description": desc_val,
        "latitude": lat_val,
        "longitude": lng_val,
        "image_url": img_url,
        "user_id": user_val, # user_id 문자열 저장 반영
        "status": "신청중",
        "recommend_count": 1,
        "heart": 1
    }

    supabase = get_supabase()
    if supabase:
        try:
            res = supabase.table("citizen_recommendations").insert(raw_record).execute()
            if res.data and len(res.data) > 0:
                inserted = normalize_citizen_record(res.data[0])
                CITIZEN_RECOMMENDATIONS_DB.append(inserted)
                return {
                    "message": "시민 추천 문화유산이 Supabase DB(citizen_recommendations)에 성공적으로 저장되었습니다.",
                    "record": inserted
                }
        except Exception as e:
            print(f"Supabase citizen_recommendations insert notice: {e}")

    new_record = normalize_citizen_record(raw_record)
    CITIZEN_RECOMMENDATIONS_DB.append(new_record)
    return {
        "message": "시민 추천 문화유산이 성공적으로 접수되었습니다.",
        "record": new_record
    }

from app.database import get_supabase

@router.get("/api/citizen-recommendations")
def get_citizen_recommendations(
    status: Optional[str] = Query(None, description="신청중 / 승인 / 반려 / pending / approved"),
    limit: Optional[int] = Query(10, description="최신 항목 조회 수 (기본 10개)")
):
    """시민 추천 목록 조회 (Supabase DB `citizen_recommendations` 테이블 연동)"""
    supabase = get_supabase()
    if supabase:
        try:
            query = supabase.table("citizen_recommendations").select("*")
            if status:
                query = query.eq("status", status)
            if limit:
                query = query.limit(limit)
            res = query.execute()
            if res.data is not None:
                return [normalize_citizen_record(r) for r in res.data]
        except Exception as e:
            print(f"Supabase citizen_recommendations query error: {e}")

    records = [normalize_citizen_record(r) for r in CITIZEN_RECOMMENDATIONS_DB]
    if status:
        records = [r for r in records if r["status"] == status]
    if limit:
        records = records[:limit]
    return records

@router.get("/api/my-recommendations/{user_id}")
def get_my_recommendations(user_id: str):
    """내가 추천한 문화유산 목록 및 등재 피드백 상태 조회"""
    records = [normalize_citizen_record(r) for r in CITIZEN_RECOMMENDATIONS_DB]
    return [r for r in records if r["user_id"] == user_id or r["submitted_by"] == user_id]

@router.post("/api/citizen-recommendations/{rec_id}/heart")
def increment_citizen_heart(rec_id: str, heart_count: Optional[int] = None):
    """시민 제보 유산 좋아요(heart) 1증가 및 수치 동기화"""
    supabase = get_supabase()
    if supabase:
        try:
            if heart_count is not None:
                new_val = heart_count
            else:
                curr_res = supabase.table("citizen_recommendations").select("heart").eq("id", rec_id).execute()
                curr_val = 0
                if curr_res.data and len(curr_res.data) > 0:
                    curr_val = curr_res.data[0].get("heart") or 0
                new_val = curr_val + 1

            res = supabase.table("citizen_recommendations").update({"heart": new_val}).eq("id", rec_id).execute()
            return {"status": "success", "id": rec_id, "heart": new_val}
        except Exception as e:
            print(f"Error updating heart for {rec_id}: {e}")
            return {"status": "error", "message": str(e)}
    return {"status": "error", "message": "Supabase not connected"}
