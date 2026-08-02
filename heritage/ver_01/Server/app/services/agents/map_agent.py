"""
app/services/agents/map_agent.py
Map Agent 모듈: 방문지의 지리 좌표(위경도) 추출 및 검증, 지도상 마커(Marker)와 이동선(Polyline)의 구간별 경로 생성
"""

from typing import Dict, Any, List
from app.services.agents.tools import get_routing_data, calculate_haversine_distance
from app.services.agents.models import MapResult, MapPoint, RouteSegment

def geocode_place(name: str, address: str) -> Dict[str, float]:
    """주소를 위도, 경도로 변환 (Kakao Local API 연동 지원 또는 Mock 좌표 매핑)"""
    # 1. Mock 대표 좌표 사전 매핑 (세종시 주요 지역 범위)
    default_coordinates = {
        "연기아문": {"lat": 36.5165, "lng": 127.2625},
        "연기아문 (동헌)": {"lat": 36.5165, "lng": 127.2625},
        "비암사": {"lat": 36.6342, "lng": 127.2023},
        "비암사 극락보전": {"lat": 36.6342, "lng": 127.2023},
        "세종 비암사 (극락보전)": {"lat": 36.6342, "lng": 127.2023},
        "초려이유태역사공원": {"lat": 36.5012, "lng": 127.2601},
        "초려 이유태 역사공원": {"lat": 36.5012, "lng": 127.2601},
        "초려공원": {"lat": 36.5012, "lng": 127.2601},
        "금남 용포리 옛 우물터": {"lat": 36.4682, "lng": 127.2785},
        "용포리 우물터": {"lat": 36.4682, "lng": 127.2785},
        "전의 운주산성": {"lat": 36.6501, "lng": 127.2155},
        "운주산성": {"lat": 36.6501, "lng": 127.2155},
        "세종호수공원": {"lat": 36.5042, "lng": 127.2678},
        "국립세종수목원": {"lat": 36.4958, "lng": 127.2867},
        "세종중앙공원": {"lat": 36.4930, "lng": 127.2710},
        "금강보행교 (이응다리)": {"lat": 36.4885, "lng": 127.2712},
        "고복자연공원": {"lat": 36.5982, "lng": 127.2285},
        "뒤웅박고을": {"lat": 36.6345, "lng": 127.2764},
        "전의 왕의물 시장": {"lat": 36.6785, "lng": 127.2012},
        "조치원 문화정원": {"lat": 36.6025, "lng": 127.3005},
        "세종 맛찬 석갈비": {"lat": 36.4812, "lng": 127.2915},
        "호수전망 가로수 카페": {"lat": 36.5055, "lng": 127.2612}
    }
    
    # 2. Kakao Map API 키가 설정된 경우 지오코딩 조회
    # (실제 주소 기반 위경도 검색 기능 탑재)
    import requests
    from app.config import settings
    if settings.KAKAO_REST_API_KEY:
        url = "https://dapi.kakao.com/v2/local/search/address.json"
        headers = {"Authorization": f"KakaoAK {settings.KAKAO_REST_API_KEY}"}
        params = {"query": address or name}
        try:
            res = requests.get(url, params=params, headers=headers, timeout=3)
            if res.status_code == 200:
                documents = res.json().get("documents", [])
                if documents:
                    return {
                        "lat": float(documents[0]["y"]),
                        "lng": float(documents[0]["x"])
                    }
        except Exception as e:
            print(f"Kakao Geocoding API notice: {e}")

    # 매핑 데이터 룩업
    for k, v in default_coordinates.items():
        if k in name or name in k:
            return v
            
    # 매핑 안될 시 세종시 기본 한가운데 좌표
    return {"lat": 36.50, "lng": 127.26}

def validate_sejong_bounds(lat: float, lng: float) -> bool:
    """좌표가 세종특별자치시 행정구역 경계 범위 내에 존재하는지 검증"""
    # 세종시 범위 대략적 사각형 바운더리
    min_lat, max_lat = 36.35, 36.75
    min_lng, max_lng = 127.10, 127.45
    return min_lat <= lat <= max_lat and min_lng <= lng <= max_lng

def map_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Map Agent Node: 위경도 매핑 검증 및 구간별 경로 Polyline 데이터 생성"""
    draft = state.get("draft_plan") or {}
    schedule = draft.get("schedule", [])
    
    if not schedule:
        return state
        
    waypoints = []
    markers = []
    
    # 1. 각 방문지 위경도 매핑 및 검증
    for idx, item in enumerate(schedule):
        coords = geocode_place(item["place_name"], item["address"])
        lat = coords["lat"]
        lng = coords["lng"]
        
        # 세종시 경계 유효성 검사 적용
        is_valid_sejong = validate_sejong_bounds(lat, lng)
        if not is_valid_sejong:
            print(f"[Map Agent] Warning: Coord for {item['place_name']} ({lat}, {lng}) is out of Sejong boundary.")
            
        # 마커 종류 설정
        # S: 출발지 | H: 문화유산 | A: 관광지 | F: 식당 | C: 카페 | E: 종료지
        ptype = item["place_type"]
        if idx == 0:
            mtype = "S"
        elif idx == len(schedule) - 1:
            mtype = "E"
        elif ptype == "heritage":
            mtype = "H"
        elif ptype == "attraction":
            mtype = "A"
        elif ptype == "food":
            mtype = "F"
        elif ptype == "cafe":
            mtype = "C"
        else:
            mtype = "A"
            
        waypoints.append({
            "name": item["place_name"],
            "lat": lat,
            "lng": lng
        })
        
        markers.append({
            "order": item["order"],
            "place_name": item["place_name"],
            "latitude": lat,
            "longitude": lng,
            "marker_type": mtype,
            "address": item["address"]
        })
        
    # 2. Kakao Map / TMap API 경로 생성
    mode = state.get("user_profile", {}).get("transport_type", "car")
    routing = get_routing_data(waypoints, mode=mode)
    
    # 3. 지도 중심좌표 및 줌레벨 계산
    lats = [pt["lat"] for pt in waypoints]
    lngs = [pt["lng"] for pt in waypoints]
    center_lat = sum(lats) / max(len(lats), 1)
    center_lng = sum(lngs) / max(len(lngs), 1)
    
    # 거리 편차에 따른 줌레벨 룰베이스 매핑
    lat_diff = max(lats) - min(lats)
    if lat_diff > 0.3:
        zoom = 8
    elif lat_diff > 0.15:
        zoom = 7
    else:
        zoom = 6
        
    map_result = {
        "center_latitude": round(center_lat, 6),
        "center_longitude": round(center_lng, 6),
        "zoom_level": zoom,
        "markers": markers,
        "routes": routing["segments"],
        "total_distance_meters": routing["total_distance_meters"],
        "total_duration_seconds": routing["total_duration_seconds"]
    }
    
    # 구간별 소요시간을 스케줄 타임라인에 업데이트
    updated_schedule = []
    current_time_min = 9 * 60 # 09:00 출발 고정
    
    for idx, item in enumerate(schedule):
        item_copy = item.copy()
        if idx == 0:
            item_copy["travel_minutes_from_previous"] = 0
        else:
            # routing segments 에서 이전구간 duration 환산
            seg_duration_sec = routing["segments"][idx-1]["duration_seconds"]
            seg_duration_min = max(int(seg_duration_sec / 60), 5) # 최소 5분 보정
            item_copy["travel_minutes_from_previous"] = seg_duration_min
            
        # 타임라인 누적 갱신
        arrival = current_time_min + item_copy["travel_minutes_from_previous"]
        departure = arrival + item_copy["stay_minutes"]
        
        def format_min(m: int) -> str:
            return f"{m // 60:02d}:{m % 60:02d}"
            
        item_copy["arrival_time"] = format_min(arrival)
        item_copy["departure_time"] = format_min(departure)
        
        current_time_min = departure
        updated_schedule.append(item_copy)
        
    # 스케줄 정보 갱신
    state["draft_plan"]["schedule"] = updated_schedule
    state["draft_plan"]["estimated_travel_minutes"] = int(routing["total_duration_seconds"] / 60)
    
    state["map_points"] = markers
    state["route_segments"] = routing["segments"]
    state["map_result"] = map_result
    
    return state
