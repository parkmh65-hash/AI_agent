"""
app/services/recommendation_service.py
Supabase DB 기반 문화유산 연관 관계 (거리, 동일시대, 동일지역) 분석 및 코스 추천 서비스
"""

import math
from typing import List, Dict, Any
from app.database import get_supabase

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 위경도 간의 하버사인 거리(km) 계산"""
    R = 6371.0  # 지구 반지름 (km)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def recommend_course(start_heritage_id: str, max_items: int = 3) -> List[Dict[str, Any]]:
    """Supabase DB를 조회하여 거리, 동일 시대, 동일 지역 등을 기준으로 연관 문화유산 추천"""
    supabase = get_supabase()
    
    all_heritages = []
    if supabase:
        try:
            res = supabase.table("heritages").select("*, images:heritage_images(*)").execute()
            if res.data:
                all_heritages = res.data
        except Exception as e:
            print(f"Supabase query notice: {e}")

    if not all_heritages:
        return []

    # 1. 출발지 문화유산 찾기
    start_item = None
    for h in all_heritages:
        if str(h.get('id')) == start_heritage_id or str(h.get('h_id')) == start_heritage_id:
            start_item = h
            break
            
    if not start_item:
        start_item = all_heritages[0]

    start_lat = float(start_item.get("latitude") or start_item.get("lat") or 36.52)
    start_lon = float(start_item.get("longitude") or start_item.get("lng") or 127.27)
    start_era = start_item.get("era") or start_item.get("era_normalized") or ""
    start_dong = start_item.get("dong") or start_item.get("dong_eup_myeon") or ""

    # 2. 다른 문화유산 후보군 점수화 및 정렬
    candidates = []
    for h in all_heritages:
        h_id = str(h.get('id'))
        if h_id == str(start_item.get('id')):
            continue

        lat = float(h.get("latitude") or h.get("lat") or 36.52)
        lon = float(h.get("longitude") or h.get("lng") or 127.27)
        era = h.get("era") or h.get("era_normalized") or ""
        dong = h.get("dong") or h.get("dong_eup_myeon") or ""

        # 가중치 계산: 거리 점수 + 속성 일치도
        dist = haversine_distance(start_lat, start_lon, lat, lon)
        
        # 기본 점수: 거리가 가까울수록 높음 (최대 100점, 거리 20km 기준 감쇄)
        score = max(0.0, 100.0 - (dist * 5))
        
        # 시대가 같으면 가산점
        if start_era and era == start_era:
            score += 30.0
            
        # 동일 읍면동인 경우 가산점
        if start_dong and dong == start_dong:
            score += 20.0

        h["distance_km"] = round(dist, 2)
        candidates.append((score, h))

    # 점수 높은 순으로 정렬
    candidates.sort(key=lambda x: x[0], reverse=True)

    # 출발 유산 포함하여 결과 리스트 작성
    recommended_items = [start_item]
    for _, item in candidates:
        recommended_items.append(item)
        if len(recommended_items) >= max_items:
            break

    return recommended_items
