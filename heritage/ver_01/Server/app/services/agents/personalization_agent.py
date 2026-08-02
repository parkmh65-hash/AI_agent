"""
app/services/agents/personalization_agent.py
Personalization Agent 모듈: 사용자의 여행자 프로필, 관심사, 동행(아동, 고령자, 반려동물) 여부를 반영하여 장소별 적합도 점수 연산
"""

from typing import Dict, Any, List

def personalization_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Personalization Agent Node: 사용자 프로필 분석 및 추천 장소별 가중 점수 연산"""
    profile = state.get("user_profile") or {}
    travel_type = profile.get("travel_type", "family")
    companions = profile.get("companions", [])
    interests = profile.get("interests", [])
    pet_companion = profile.get("pet_companion", False)
    child_companion = profile.get("child_companion", False)
    
    print(f"[Personalization Agent] Tailoring for: {travel_type} (Pet={pet_companion}, Child={child_companion})")
    
    heritages = state.get("selected_heritages", [])
    personalized_heritages = []
    
    for h in heritages:
        name = h["heritage_name"]
        desc = h["description"]
        
        # 1. 개인화 점수 계산 공식 적용
        # 관심사 일치도(30점) + 동행유형 적합도(25점) + 접근성(15점) + 체력조건 적합도(10점) + 식사/편의시설(10점) + 날씨(10점)
        interest_score = 0.0
        companion_score = 0.0
        accessibility_score = 15.0 if not profile.get("accessibility_required", False) else 5.0
        stamina_score = 10.0
        
        # 1.1 관심사 일치도 채점
        if "history" in interests and any(w in desc for w in ["역사", "유적", "조선", "백제", "문화재"]):
            interest_score += 30.0
        elif "nature" in interests and any(w in desc for w in ["산성", "공원", "수목원", "숲", "정원"]):
            interest_score += 30.0
        elif "experience" in interests and any(w in desc for w in ["체험", "마을", "시장", "발굴"]):
            interest_score += 30.0
        else:
            interest_score += 20.0 # 기본값
            
        # 1.2 동행 유형 채점
        if travel_type == "family":
            # 주차 및 평지 위주 장소 우대
            if any(w in name for w in ["공원", "아문", "역사공원"]):
                companion_score += 25.0
            else:
                companion_score += 18.0
        elif travel_type == "couple":
            # 한옥 감성, 호수, 야경 우대
            if any(w in name for w in ["비암사", "역사공원", "우물터"]):
                companion_score += 25.0
            else:
                companion_score += 20.0
        elif travel_type == "solo":
            # 조용한 사색 장소 우대
            if "비암사" in name or "산성" in name:
                companion_score += 25.0
            else:
                companion_score += 15.0
        else:
            companion_score += 20.0
            
        # 반려동물 동반 시 야외 공간(산성, 공원) 점수 상향, 실내/사찰 하향
        if pet_companion:
            if "산성" in name or "공원" in name:
                companion_score += 5.0
                stamina_score += 5.0
            elif "비암사" in name or "박물관" in name:
                companion_score -= 10.0 # 반려동물 제한 가능성 반영
                
        # 어린이 동반 시 험난한 산성 하향, 공원 상향
        if child_companion:
            if "산성" in name:
                stamina_score -= 5.0
            elif "공원" in name or "우물터" in name:
                stamina_score += 5.0
                
        total_score = interest_score + companion_score + accessibility_score + stamina_score + 10.0 + 10.0 # 식사/날씨 가점 기본 포함
        total_score = round(min(total_score, 100.0), 1)
        
        # 개인화 이유 생성
        reason = f"{travel_type} 동행의 선호 유형에 잘 들어맞으며"
        if pet_companion and ("산성" in name or "공원" in name):
            reason += " 반려동물이 신나게 산책하기에 최적화된 개방형 야외 장소입니다."
        elif child_companion and "산성" in name:
            reason += " 단, 경사가 다소 있어 유모차나 유아 동반 시 도보 이동에 주의가 필요합니다."
        else:
            reason += " 문화재와 경관이 조화롭게 어우러져 여유로운 관람이 가능합니다."
            
        h_copy = h.copy()
        h_copy["personalization_score"] = total_score
        h_copy["personalization_reason"] = reason
        personalized_heritages.append(h_copy)
        
    # 적합도 높은 순으로 재정렬
    personalized_heritages.sort(key=lambda x: x.get("personalization_score", 0.0), reverse=True)
    state["selected_heritages"] = personalized_heritages
    state["personalized_plan"] = {
        "status": "customized",
        "travel_type": travel_type,
        "pet_companion": pet_companion,
        "child_companion": child_companion,
        "customization_reasons": [h["personalization_reason"] for h in personalized_heritages]
    }
    
    return state
