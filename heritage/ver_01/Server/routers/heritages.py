"""
app/routers/heritages.py
문화유산 목록 조회, 필터(동읍면, 시대, 키워드), 상세조회 및 시각화 통계 API
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from app.database import get_supabase

router = APIRouter(prefix="/api/heritages", tags=["heritages"])

@router.get("", response_model=List[Dict[str, Any]])
def get_heritages(
    dong_eup_myeon: Optional[str] = Query(None, description="읍면동 필터 (예: 연기면, 어진동)"),
    era_normalized: Optional[str] = Query(None, description="정규화 시대 필터 (예: 조선 전기, 청동기시대)"),
    keyword: Optional[str] = Query(None, description="검색 키워드")
):
    """문화유산 목록 및 다중 조건 필터링"""
    supabase = get_supabase()
    if supabase:
        try:
            query_builder = supabase.table("heritages").select("*, images:heritage_images(*)")
            if dong_eup_myeon:
                query_builder = query_builder.eq("dong", dong_eup_myeon)
            if era_normalized:
                query_builder = query_builder.eq("era", era_normalized)
            if keyword:
                query_builder = query_builder.ilike("name", f"%{keyword}%")
            res = query_builder.execute()
            if res.data is not None:
                return res.data
        except Exception as e:
            print(f"Supabase fetch error: {e}")

    return []

@router.get("/stats")
def get_heritage_stats():
    """세종시 실시간 문화유산 현황 통계 요약 (읍면동별, 시대별 그래프용)"""
    supabase = get_supabase()
    heritages = []
    if supabase:
        try:
            res = supabase.table("heritages").select("*").execute()
            if res.data:
                heritages = res.data
        except Exception as e:
            print(f"Stats query notice: {e}")

    total_count = len(heritages)
    era_counts = {}
    dong_counts = {}
    
    for h in heritages:
        era = h.get("era") or "시대 미상"
        dong = h.get("dong") or "세종특별자치시"
        era_counts[era] = era_counts.get(era, 0) + 1
        dong_counts[dong] = dong_counts.get(dong, 0) + 1

    era_chart_data = [{"era": k, "count": v} for k, v in era_counts.items()]
    dong_chart_data = [{"dong": k, "count": v} for k, v in dong_counts.items()]

    return {
        "total_count": total_count,
        "national_registered_count": total_count,
        "era_stats": era_chart_data,
        "dong_stats": dong_chart_data
    }

@router.get("/{heritage_id}")
def get_heritage_detail(heritage_id: str):
    """문화유산 단건 상세 정보 조회"""
    supabase = get_supabase()
    if supabase:
        try:
            res = supabase.table("heritages").select("*, images:heritage_images(*)").eq("id", heritage_id).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
        except Exception as e:
            print(f"Detail query notice: {e}")

    raise HTTPException(status_code=404, detail="문화유산을 찾을 수 없습니다.")

@router.post("/{heritage_id}/like")
@router.post("/{heritage_id}/heart")
def increment_heritage_like(heritage_id: str, like_count: Optional[int] = Query(None, description="업데이트할 좋아요 수치")):
    """공식 문화유산 좋아요(like_count) 서버 경유 Supabase DB 반영"""
    supabase = get_supabase()
    if supabase:
        try:
            if like_count is not None:
                new_val = like_count
            else:
                curr_res = supabase.table("heritages").select("like_count").eq("id", heritage_id).execute()
                curr_val = 50
                if curr_res.data and len(curr_res.data) > 0:
                    curr_val = curr_res.data[0].get("like_count") or 50
                new_val = curr_val + 1

            res = supabase.table("heritages").update({"like_count": new_val}).eq("id", heritage_id).execute()
            return {"status": "success", "id": heritage_id, "like_count": new_val, "updated_via": "server_supabase"}
        except Exception as e:
            print(f"Error updating like for heritage {heritage_id}: {e}")
            return {"status": "error", "detail": str(e), "like_count": like_count or 50}

    return {"status": "mock", "id": heritage_id, "like_count": like_count or 50}
