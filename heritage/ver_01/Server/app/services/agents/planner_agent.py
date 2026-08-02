"""
app/services/agents/planner_agent.py
Planner Agent 모듈: 선정된 문화유산(5곳)과 TourAPI 주변 관광지(최대 10곳)의 매핑 및 시간대별 기초 여행 일정(Draft Plan) 조립
"""

from typing import Dict, Any, List
from app.services.agents.tools import search_tourapi_nearby
from app.services.agents.models import TravelPlan, ScheduleItem

def planner_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Planner Agent Node: 주변 관광지 매핑 및 타임라인 스케줄 초안 구성"""
    heritages = state.get("selected_heritages", [])
    
    # 1. 5개 문화유산 필수 선정
    selected_heritages = heritages[:5]
    
    # 2. 각 문화유산 주변의 관광지/식당 검색 및 중복 제거
    nearby_spots = []
    seen_names = set()
    
    radius_km = float(state.get("user_profile", {}).get("radius_km", 5.0))
    for h in selected_heritages:
        # 문화유산 좌표 획득
        lat = h.get("latitude")
        lng = h.get("longitude")
        
        # 주소 파싱 또는 candidates/retrieved_documents에서 매핑 정보 추출
        if not lat or not lng:
            # retrieved_documents에서 좌표 찾아보기
            found = False
            for doc in state.get("retrieved_documents", []):
                meta = doc.get("metadata", {})
                if meta.get("name") == h["heritage_name"]:
                    lat = meta.get("latitude")
                    lng = meta.get("longitude")
                    h["latitude"] = lat
                    h["longitude"] = lng
                    found = True
                    break
            if not found:
                # 기본 좌표 부여
                lat, lng = 36.52, 127.27
                h["latitude"] = lat
                h["longitude"] = lng
                
        spots = search_tourapi_nearby(lat, lng, radius_km=radius_km)
        for s in spots:
            if s["name"] not in seen_names:
                seen_names.add(s["name"])
                # 인접 문화유산 기록
                s["linked_heritage"] = h["heritage_name"]
                nearby_spots.append(s)
                
    # 최대 10개로 제한
    selected_attractions = nearby_spots[:10]
    
    # 3. 시간대별 기초 타임라인 구성 (기본 09:00 ~ 19:00 규칙)
    profile = state.get("user_profile", {})
    start_time_str = profile.get("start_time", "09:00")
    end_time_str = profile.get("end_time", "19:00")
    
    try:
        start_hour, start_min = map(int, start_time_str.split(":"))
    except Exception:
        start_hour, start_min = 9, 0
        
    schedule = []
    current_time_minutes = start_hour * 60 + start_min
    
    def minutes_to_hhmm(m: int) -> str:
        return f"{m // 60:02d}:{m % 60:02d}"
        
    # 세그먼트 스케줄러 빌더
    order = 1
    # 3.1 오전 일정
    if selected_heritages:
        h1 = selected_heritages[0]
        stay = 50
        schedule.append({
            "order": order,
            "place_name": h1["heritage_name"],
            "place_type": "heritage",
            "address": h1["address"],
            "arrival_time": minutes_to_hhmm(current_time_minutes),
            "departure_time": minutes_to_hhmm(current_time_minutes + stay),
            "stay_minutes": stay,
            "travel_minutes_from_previous": 0,
            "reason": f"오전 첫 코스로 고즈넉하고 역사적 정취가 깊은 {h1['heritage_name']} 탐방"
        })
        current_time_minutes += stay
        order += 1
        
    # 주변 관광지 1
    attractions_only = [s for s in selected_attractions if s["type"] == "attraction"]
    if attractions_only:
        a1 = attractions_only[0]
        travel = 20
        stay = 60
        current_time_minutes += travel
        schedule.append({
            "order": order,
            "place_name": a1["name"],
            "place_type": "attraction",
            "address": a1["address"],
            "arrival_time": minutes_to_hhmm(current_time_minutes),
            "departure_time": minutes_to_hhmm(current_time_minutes + stay),
            "stay_minutes": stay,
            "travel_minutes_from_previous": travel,
            "reason": f"인근의 대표 명소인 {a1['name']}를(을) 가볍게 걸으며 감상"
        })
        current_time_minutes += stay
        order += 1
        
    # 점심 식사
    food_only = [s for s in selected_attractions if s["type"] in ["food", "cafe"]]
    lunch_place = "세종시 향토 석갈비 전문점"
    lunch_addr = "세종특별자치시 보람동"
    if food_only:
        lunch_place = food_only[0]["name"]
        lunch_addr = food_only[0]["address"]
        
    travel = 15
    stay = 60
    current_time_minutes += travel
    schedule.append({
        "order": order,
        "place_name": lunch_place,
        "place_type": "food",
        "address": lunch_addr,
        "arrival_time": minutes_to_hhmm(current_time_minutes),
        "departure_time": minutes_to_hhmm(current_time_minutes + stay),
        "stay_minutes": stay,
        "travel_minutes_from_previous": travel,
        "reason": "지역 향토 요리를 맛보며 편안한 점심 식사와 휴식"
    })
    current_time_minutes += stay
    order += 1
    
    # 3.2 오후 일정
    if len(selected_heritages) > 1:
        h2 = selected_heritages[1]
        travel = 25
        stay = 60
        current_time_minutes += travel
        schedule.append({
            "order": order,
            "place_name": h2["heritage_name"],
            "place_type": "heritage",
            "address": h2["address"],
            "arrival_time": minutes_to_hhmm(current_time_minutes),
            "departure_time": minutes_to_hhmm(current_time_minutes + stay),
            "stay_minutes": stay,
            "travel_minutes_from_previous": travel,
            "reason": f"오후 주 코스로 학술적/문화적 보존 가치가 큰 {h2['heritage_name']} 관람"
        })
        current_time_minutes += stay
        order += 1
        
    if len(attractions_only) > 1:
        a2 = attractions_only[1]
        travel = 20
        stay = 50
        current_time_minutes += travel
        schedule.append({
            "order": order,
            "place_name": a2["name"],
            "place_type": "attraction",
            "address": a2["address"],
            "arrival_time": minutes_to_hhmm(current_time_minutes),
            "departure_time": minutes_to_hhmm(current_time_minutes + stay),
            "stay_minutes": stay,
            "travel_minutes_from_previous": travel,
            "reason": f"자연 경관이 수려한 {a2['name']}에서 산책 및 힐링"
        })
        current_time_minutes += stay
        order += 1
        
    # 카페 타임
    cafe_place = "호수전망 가로수 카페"
    cafe_addr = "세종특별자치시 한누리대로"
    cafes = [s for s in selected_attractions if s["type"] == "cafe"]
    if cafes:
        cafe_place = cafes[0]["name"]
        cafe_addr = cafes[0]["address"]
    elif len(food_only) > 1:
        cafe_place = food_only[1]["name"]
        cafe_addr = food_only[1]["address"]
        
    travel = 15
    stay = 45
    current_time_minutes += travel
    schedule.append({
        "order": order,
        "place_name": cafe_place,
        "place_type": "cafe",
        "address": cafe_addr,
        "arrival_time": minutes_to_hhmm(current_time_minutes),
        "departure_time": minutes_to_hhmm(current_time_minutes + stay),
        "stay_minutes": stay,
        "travel_minutes_from_previous": travel,
        "reason": "차량 이동 후 피로를 덜고 대화를 나눌 수 있는 감성 카페 휴식"
    })
    current_time_minutes += stay
    order += 1
    
    # 3.3 저녁 일정
    if len(selected_heritages) > 2:
        h3 = selected_heritages[2]
        travel = 30
        stay = 50
        current_time_minutes += travel
        schedule.append({
            "order": order,
            "place_name": h3["heritage_name"],
            "place_type": "heritage",
            "address": h3["address"],
            "arrival_time": minutes_to_hhmm(current_time_minutes),
            "departure_time": minutes_to_hhmm(current_time_minutes + stay),
            "stay_minutes": stay,
            "travel_minutes_from_previous": travel,
            "reason": f"일정 마지막 코스로 주변 전망과 성벽 낙조가 고풍스러운 {h3['heritage_name']} 탐방"
        })
        current_time_minutes += stay
        order += 1
        
    # 4. 구조화된 TravelPlan 구성
    total_stay = sum(item["stay_minutes"] for item in schedule)
    total_travel = sum(item["travel_minutes_from_previous"] for item in schedule)
    
    draft = {
        "title": f"세종시 AI 문화유산 및 {profile.get('travel_type', '가족')} 맞춤형 당일 추천 여행 코스",
        "start_time": start_time_str,
        "end_time": minutes_to_hhmm(current_time_minutes),
        "heritage_count": len([i for i in schedule if i["place_type"] == "heritage"]),
        "attraction_count": len([i for i in schedule if i["place_type"] == "attraction"]),
        "schedule": schedule,
        "total_stay_minutes": total_stay,
        "estimated_travel_minutes": total_travel
    }
    
    state["nearby_attractions"] = selected_attractions
    state["draft_plan"] = draft
    state["selected_heritages"] = selected_heritages
    
    return state
