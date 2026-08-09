"""
app/services/agents/rag_agent.py
RAG Agent 모듈: 벡터 데이터베이스(Supabase pgvector) 조회 및 관련성 평가, 필요 시 검색어 재작성(Rewrite) 수행
"""

from typing import Dict, Any, List
from app.config import settings
from app.services.agents.tools import retrieve_vector_db
from app.services.agents.models import HeritageSearchResult, RAGAgentResult

def get_llm(model_name: str = "gpt-4o"):
    """LLM 인스턴스 획득 (OpenAI -> Gemini -> Fallback None)"""
    if settings.OPENAI_API_KEY:
        from langchain_openai import ChatOpenAI
        # gpt-4o 또는 gpt-4o-mini 지원
        model = model_name if model_name in ["gpt-4o", "gpt-4o-mini"] else "gpt-4o"
        return ChatOpenAI(openai_api_key=settings.OPENAI_API_KEY, model=model, temperature=0, max_retries=0, timeout=10.0)
    elif settings.GEMINI_API_KEY:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(google_api_key=settings.GEMINI_API_KEY, model="gemini-1.5-flash", temperature=0, timeout=10.0)
    return None

def rag_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """RAG Agent Node: 사용자 질문에 따른 문화유산 검색 및 관련성 채점"""
    query = state.get("rewritten_query") or state.get("user_query")
    print(f"[RAG Agent] Searching for: {query}")
    
    # 1. Supabase Vector Store / DB 검색
    search_k = int(settings.DEFAULT_SEARCH_K)
    documents = retrieve_vector_db(query, k=search_k)
    
    # 2. LLM을 통한 관련성 채점 (Structured Output 적용)
    llm = get_llm("gpt-4o-mini")
    selected_heritages = []
    confidence_score = 0.0
    
    if llm:
        try:
            # Pydantic 구조 강제 호출 (Structured Output)
            structured_llm = llm.with_structured_output(RAGAgentResult)
            prompt = f"""
            사용자의 세종시 문화유산 관련 질의: "{query}"
            
            아래 수집된 데이터 문서 목록을 평가하고 질문에 맞는 적절한 문화유산 목록을 최대 5개 구성하여 구조화된 형식으로 반환하십시오.
            각 문화유산별로 질문과의 관련성 점수(relevance_score, 0~1) 및 데이터 신뢰성 점수(confidence_score, 0~1)를 부여하십시오.
            
            [수집 문서 목록]
            {documents}
            """
            llm_result = structured_llm.invoke(prompt)
            selected_heritages = [h.dict() for h in llm_result.selected_heritages]
            confidence_score = llm_result.confidence_score
        except Exception as e:
            print(f"[RAG Agent] LLM Grading failed: {e}. Falling back to Rule-based parsing.")
            
    # 3. LLM이 비활성화되거나 실패 시 룰 베이스 파싱 및 추천 매칭
    if not selected_heritages:
        for idx, doc in enumerate(documents):
            meta = doc["metadata"]
            name = meta.get("name", "지정문화유산")
            addr = meta.get("address", "세종시")
            era = meta.get("era", "조선시대")
            desc = doc.get("content", "")
            
            # 단순 룰기반 관련성 매칭 점수
            rel_score = 0.9 if any(w in query for w in name.split()) else 0.6
            
            selected_heritages.append({
                "heritage_name": name,
                "category": meta.get("source", "registered"),
                "address": addr,
                "description": desc,
                "historical_value": f"세종시 {dong_or_name(meta)} 소재 {era} 유산",
                "source_url": f"https://www.heritage.go.kr/search?query={name}",
                "relevance_score": rel_score,
                "confidence_score": 0.8
            })
        
    # 3. 5개 미만인 경우 Supabase DB에서 추가 동적 조회 보완 (하드코딩 모의데이터 100% 제거)
    if len(selected_heritages) < 5:
        try:
            from app.services.agents.tools import get_supabase_client
            supabase = get_supabase_client()
            if supabase:
                # heritages 테이블 동적 조회
                res = supabase.table("heritages").select("*").limit(10).execute()
                for row in (res.data or []):
                    if len(selected_heritages) >= 5:
                        break
                    h_name = row.get("name") or row.get("heritage_name") or "세종시 문화유산"
                    if not any(h.get("heritage_name") == h_name for h in selected_heritages):
                        selected_heritages.append({
                            "heritage_name": h_name,
                            "category": row.get("category") or row.get("era") or "공식 지정 유산",
                            "address": row.get("address") or row.get("dong_eup_myeon") or "세종특별자치시",
                            "description": row.get("description") or row.get("reason") or "Supabase DB 등록 세종시 대표 문화유산입니다.",
                            "relevance_score": 0.85,
                            "confidence_score": 0.85
                        })
                # citizen_recommendations 테이블 동적 조회
                if len(selected_heritages) < 5:
                    c_res = supabase.table("citizen_recommendations").select("*").limit(5).execute()
                    for c_row in (c_res.data or []):
                        if len(selected_heritages) >= 5:
                            break
                        c_name = c_row.get("name") or c_row.get("heritage_name") or "시민 발굴 유산"
                        if not any(h.get("heritage_name") == c_name for h in selected_heritages):
                            selected_heritages.append({
                                "heritage_name": c_name,
                                "category": "시민 제보 유산",
                                "address": c_row.get("address") or c_row.get("dong") or "세종특별자치시",
                                "description": c_row.get("reason") or c_row.get("description") or "Supabase DB 등록 시민 발굴 소중한 유산입니다.",
                                "relevance_score": 0.82,
                                "confidence_score": 0.80
                            })
        except Exception as err:
            print(f"[RAG Agent] Dynamic DB complement notice: {err}")

    selected_heritages = selected_heritages[:5]
    confidence_score = sum(h.get("relevance_score", 0.8) for h in selected_heritages) / max(len(selected_heritages), 1)

    # RAG 피드백 검증용 상태 데이터 갱신
    state["retrieved_documents"] = documents
    state["heritage_candidates"] = selected_heritages
    state["selected_heritages"] = selected_heritages
    state["confidence_score"] = confidence_score
    
    # 4단계 질문 재작성 조건 체크 (평균 점수 0.6 미만 또는 문서 부족 시)
    if len(documents) < 3 or confidence_score < 0.6:
        state["grade_score"] = "no"
        print(f"[RAG Agent] Low confidence ({confidence_score:.2f}). Needs rewrite.")
    else:
        state["grade_score"] = "yes"
        print(f"[RAG Agent] High confidence ({confidence_score:.2f}). Proceeding to personalization.")
        
    return state

def rewrite_query_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Rewrite Node: 사용자 질문의 완성도를 높이기 위해 검색어 재작성"""
    orig_q = state.get("user_query", "")
    llm = get_llm("gpt-4o-mini")
    rewritten = ""
    
    if llm:
        try:
            prompt = f"""
            사용자의 다음 질문은 세종시 문화유산 데이터베이스(Vector Store)를 검색하기에 키워드가 모호하거나 부족합니다.
            Supabase pgvector 유사도 매칭 성능을 극대화하기 위해 역사, 문화재 유형명, 읍면동 행정구역명이 포함된 정교한 검색 문장으로 재작성해 주십시오.
            단, 다른 사설이나 인사말은 제외하고 재작성된 검색어만 단문으로 응답하십시오.
            
            사용자 기존 질문: "{orig_q}"
            """
            res = llm.invoke(prompt)
            rewritten = res.content.strip().replace('"', '')
        except Exception as e:
            print(f"[Rewrite Query] LLM Rewrite failed: {e}")
            
    if not rewritten:
        # 규칙 기반 대체 재작성
        if "볼거리" in orig_q or "추천" in orig_q:
            rewritten = "세종특별자치시 소재 국가유산, 향토문화유산 및 시민 제안 문화유산 중 역사적 가치와 관광 접근성이 높은 장소를 검색해 주세요."
        else:
            rewritten = f"세종특별자치시 {orig_q} 역사적 유적지와 지정 문화유산 관광지 추천 정보"
            
    print(f"[Rewrite Query] Rewrote: '{orig_q}' -> '{rewritten}'")
    state["rewritten_query"] = rewritten
    state["retry_count"] = state.get("retry_count", 0) + 1
    return state

def dong_or_name(meta: dict) -> str:
    return meta.get("dong") or meta.get("address", "세종시").split()[-1]
