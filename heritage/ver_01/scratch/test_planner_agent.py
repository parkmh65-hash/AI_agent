"""
heritage/ver_01/scratch/test_planner_agent.py
최종 구현한 6대 멀티 에이전트 시스템(LangGraph) 비즈니스 로직 단위 테스트 스크립트
"""

import sys
import os

# 모듈 탐색 경로를 Server 디렉토리로 맞춤
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Server")))

from app.services.agentic_rag_service import run_travel_plan

def test_multi_agent_flow():
    print("🚀 Starting Multi-Agentic RAG Travel Planner local testing...")
    
    payload = {
        "query": "세종시 전의면 문화유산 중심 당일 여행 코스 추천해줘",
        "travel_date": "2026-08-15",
        "start_location": "세종시청",
        "start_time": "09:00",
        "end_time": "19:00",
        "transport_type": "car",
        "travel_type": "family",
        "companions": ["adult", "child"],
        "interests": ["history", "nature"],
        "walking_tolerance": "medium",
        "pet_companion": False
    }
    
    try:
        result = run_travel_plan(payload)
        
        print("\n✅ Multi-Agent Workflow Completed Successfully!")
        print(f"Status: {result['status']}")
        print(f"Heritages Selected: {len(result['heritages'])}")
        for idx, h in enumerate(result['heritages'], start=1):
            print(f"  {idx}. {h['heritage_name']} (Relevance: {h['relevance_score']}, Fit: {h['personalization_score']})")
            
        print(f"\nAttractions Found: {len(result['attractions'])}")
        print(f"\nSchedule Itinerary count: {len(result['schedule'])} items")
        for item in result['schedule']:
            print(f"  [{item['arrival_time']} - {item['departure_time']}] {item['place_name']} ({item['place_type']})")
            
        print(f"\nRoute Total Distance: {result['map']['total_distance_km']} km")
        print(f"Route Total Duration: {result['map']['total_duration_minutes']} minutes")
        
        print(f"\nWeather Status: {result['real_time_info']['weather']['weather']}")
        print(f"RAG Validation Score: {result['validation']['score'] * 100}%")
        
        assert result["status"] == "success"
        assert len(result["heritages"]) > 0
        assert len(result["schedule"]) > 0
        print("\n🎉 Unit assertion check passed!")
        
    except Exception as e:
        print(f"\n❌ Error during multi-agent test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_multi_agent_flow()
