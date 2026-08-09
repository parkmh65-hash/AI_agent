"""
app/routers/heritages.py
문화유산 목록 조회, 필터(동읍면, 시대, 키워드), 상세조회 및 시각화 통계 API
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from app.database import get_supabase

router = APIRouter(prefix="/api/heritages", tags=["heritages"])

def normalize_heritage_row(row: Dict[str, Any]) -> Dict[str, Any]:
    dong_val = row.get("dong") or row.get("dong_eup_myeon") or "세종특별자치시"
    row["dong"] = dong_val
    row["dong_eup_myeon"] = dong_val
    
    era_val = row.get("era") or row.get("era_normalized") or "조선시대"
    row["era"] = era_val
    row["era_normalized"] = era_val

    thinking_val = row.get("thinking_point") or row.get("thinkingPoint") or row.get("think_about") or row.get("think_point") or ""
    row["thinking_point"] = thinking_val
    row["thinkingPoint"] = thinking_val
    row["think_about"] = thinking_val
    row["think_point"] = thinking_val

    try:
        lat_raw = row.get("latitude") or row.get("lat")
        lat_val = float(lat_raw) if lat_raw is not None and lat_raw != "" else 36.52
    except (ValueError, TypeError):
        lat_val = 36.52

    try:
        lng_raw = row.get("longitude") or row.get("lng")
        lng_val = float(lng_raw) if lng_raw is not None and lng_raw != "" else 127.27
    except (ValueError, TypeError):
        lng_val = 127.27
    row["latitude"] = lat_val
    row["lat"] = lat_val
    row["longitude"] = lng_val
    row["lng"] = lng_val

    images = row.get("images") or []
    img_url = ""
    if images and len(images) > 0:
        first_img = images[0]
        if isinstance(first_img, dict):
            img_url = first_img.get("image_url") or first_img.get("imageUrl") or ""
    if not img_url:
        img_url = row.get("image_url") or row.get("imageUrl") or row.get("supabase_storage_url") or row.get("supabaseStorageUrl") or ""

    if not img_url and row.get("h_id"):
        h_id = str(row.get("h_id")).strip()
        if h_id.startswith("H"):
            img_url = f"https://pdpmtgnagwzcsftavtap.supabase.co/storage/v1/object/public/heritage-images/{h_id}_{h_id}.jpg"

    row["image_url"] = img_url
    row["imageUrl"] = img_url
    row["supabase_storage_url"] = img_url
    row["supabaseStorageUrl"] = img_url

    row["source"] = row.get("source") or "registered"
    row["status"] = row.get("status") or "approved"
    row["like_count"] = int(row.get("like_count") or row.get("likeCount") or 50)
    return row

@router.get("", response_model=List[Dict[str, Any]])
def get_heritages(
    dong: Optional[str] = Query(None, description="읍면동 필터 (예: 연기면, 어진동)"),
    dong_eup_myeon: Optional[str] = Query(None, description="읍면동 필터 호환용"),
    era_normalized: Optional[str] = Query(None, description="정규화 시대 필터 (예: 조선 전기, 청동기시대)"),
    era: Optional[str] = Query(None, description="시대 필터"),
    keyword: Optional[str] = Query(None, description="검색 키워드")
):
    """문화유산 목록 및 다중 조건 필터링 (Supabase heritages & heritage_images 조인)"""
    target_dong = dong if isinstance(dong, str) and dong else (dong_eup_myeon if isinstance(dong_eup_myeon, str) and dong_eup_myeon else None)
    target_era = era_normalized if isinstance(era_normalized, str) and era_normalized else (era if isinstance(era, str) and era else None)
    target_kw = keyword if isinstance(keyword, str) and keyword else None
    
    supabase = get_supabase()
    if supabase:
        try:
            query_builder = supabase.table("heritages").select("*,images:heritage_images(*)")
            if target_dong:
                query_builder = query_builder.eq("dong", target_dong)
            if target_era:
                query_builder = query_builder.eq("era", target_era)
            if target_kw:
                query_builder = query_builder.ilike("name", f"%{target_kw}%")
            res = query_builder.execute()
            if res.data is not None:
                return [normalize_heritage_row(row) for row in res.data]
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
            print(f"Stats query error: {e}")

    total_count = len(heritages)
    era_counts = {}
    dong_counts = {}
    
    for h in heritages:
        era = h.get("era_normalized") or h.get("era") or "시대 미상"
        dong = h.get("dong") or h.get("dong_eup_myeon") or "세종특별자치시"
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
                return normalize_heritage_row(res.data[0])
        except Exception as e:
            print(f"Detail query error: {e}")

    raise HTTPException(status_code=404, detail="해당 문화유산을 찾을 수 없습니다.")

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

@router.post("/vectorize")
def vectorize_heritages_api():
    """Supabase heritages 테이블 전체 텍스트 벡터 임베딩 생성 및 Supabase DB 저장 실행"""
    try:
        from scripts.vectorize_heritages import vectorize_and_save_heritages
        records = vectorize_and_save_heritages()
        return {
            "status": "success",
            "message": f"총 {len(records)}건의 heritage 데이터 벡터화 및 Supabase DB 저장이 완료되었습니다.",
            "total_count": len(records)
        }
    except Exception as e:
        print(f"Vectorize API error: {e}")
        return {"status": "error", "message": str(e)}
