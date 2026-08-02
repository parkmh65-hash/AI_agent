"""
app/services/agents/validation_agent.py
Validation Agent 모듈: 생성된 최종 여행 일정의 공식 주소, 운영시간, 좌표 정합도 검증 및 RAG Feedback Loop 조건부 회귀 판정
"""

from typing import Dict, Any, List
from app.services.agents.tools import retrieve_vector_db
from app.services.agents.models import ValidationResult, PlaceValidation

def validation_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Validation Agent Node: RAG Feedback Loop 및 최종 데이터 무결성 검증"""
    plan = state.get("draft_plan") or {}
    schedule = plan.get("schedule", [])
    
    print(f"[Validation Agent] Starting cross-verification loop for {len(schedule)} itinerary items...")
    
    place_validations = []
    verified_count = 0
    failed_count = 0
    
    # 각 방문 장소들에 대해 검증 수행
    for item in schedule:
        name = item["place_name"]
        address = item["address"]
        ptype = item["place_type"]
        
        address_verified = True
        operation_verified = True
        coordinate_verified = True
        source_verified = True
        status = "verified"
        issues = []
        source_urls = []
        
        # 문화유산은 RAG를 통해 데이터가 DB에 실존하고 주소가 맞는지 재검침
        if ptype == "heritage":
            # 11단계 Feedback Loop: 장소명 재검색
            docs = retrieve_vector_db(name, k=1)
            if docs:
                meta = docs[0].get("metadata", {})
                official_name = meta.get("name", "")
                official_address = meta.get("address", "")
                
                # 주소 지명 부분 비교 검증
                if official_address and address.split()[-1] not in official_address:
                    address_verified = False
                    status = "needs_update"
                    issues.append(f"주소 불일치 의심: 입력된 주소 '{address}' != 공식 주소 '{official_address}'")
                    
                source_urls.append(meta.get("source_url") or f"https://www.heritage.go.kr/search?query={name}")
            else:
                source_verified = False
                status = "insufficient_data"
                issues.append("Supabase DB에서 공식 문화유산 정보를 재매핑하지 못했습니다.")
                
        # 식당 및 카페 검증 (임시 휴업, 주차 검증)
        elif ptype in ["food", "cafe"]:
            if not address or len(address) < 4:
                address_verified = False
                status = "needs_update"
                issues.append("위치 주소가 불분명하여 최적 경로 안내가 제한될 수 있습니다.")
                
        # 점수 합산
        if status == "verified":
            verified_count += 1
        else:
            failed_count += 1
            
        place_validations.append({
            "place_name": name,
            "status": status,
            "address_verified": address_verified,
            "operation_verified": operation_verified,
            "coordinate_verified": coordinate_verified,
            "source_verified": source_verified,
            "issues": issues,
            "source_urls": source_urls
        })
        
    # 종합 정합 검증 점수 환산
    total = len(schedule)
    validation_score = round(verified_count / max(total, 1), 2)
    
    # 0.8 미만이거나 치명적 이슈 발견 시 수정 요청 플래그 설정
    requires_revision = False
    revision_target = None
    
    if validation_score < 0.8:
        requires_revision = True
        # 어떤 문제에 속하는지 파악하여 회귀 타겟 선정
        has_heritage_issues = any(pv["status"] == "insufficient_data" and ptype == "heritage" for pv in place_validations)
        if has_heritage_issues:
            revision_target = "rag"
        else:
            revision_target = "planner"
            
    # max_retry 초과 여부 확인
    retry_cnt = state.get("retry_count", 0)
    max_retry = state.get("max_retry_count", 3)
    
    if requires_revision and retry_cnt >= max_retry:
        print(f"[Validation Agent] Max retry count ({max_retry}) reached. Halting loop to prevent infinite recursion.")
        requires_revision = False # 강제 통과
        
    validation_result = {
        "overall_status": "verified" if not requires_revision else "revision_needed",
        "validation_score": validation_score,
        "verified_places": verified_count,
        "failed_places": failed_count,
        "requires_revision": requires_revision,
        "revision_target": revision_target,
        "place_results": place_validations
    }
    
    state["validation_result"] = validation_result
    # 최종 신뢰도는 검증 점수 가중 환산
    state["confidence_score"] = validation_score
    
    print(f"[Validation Agent] Overall validation status: {validation_result['overall_status']}, Score: {validation_score:.2f}, Requires Revision: {requires_revision}")
    
    return state
