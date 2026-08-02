"""
app/services/guidebook_service.py
문화유산 관광 가이드북 스토리보드 생성을 위한 다중 에이전트 서비스 모듈
(기획 ➔ 작성 ➔ 편집 ➔ 번역의 4대 전문 에이전트 협업 체인)
"""

import os
from typing import List, Dict, Any, TypedDict
from langgraph.graph import StateGraph, END
from app.config import settings

# 1. Guidebook 상태 관리구조 정의
class GuidebookState(TypedDict):
    heritages: List[str]
    concept: str
    draft: str
    edited: str
    translated: str
    final_output: str
    steps_log: List[Dict[str, str]]

def get_llm(model_name: str = "gpt-4o"):
    """LLM 인스턴스 획득 (OpenAI -> Gemini -> Fallback None)"""
    if settings.OPENAI_API_KEY:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            openai_api_key=settings.OPENAI_API_KEY, 
            model=model_name, 
            temperature=0.3,
            max_retries=0,
            request_timeout=12
        )
    elif settings.GEMINI_API_KEY:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            google_api_key=settings.GEMINI_API_KEY, 
            model="gemini-1.5-flash", 
            temperature=0.3,
            request_timeout=12
        )
    return None

# 2. 에이전트 노드 구현

def concept_agent_node(state: GuidebookState) -> GuidebookState:
    """1단계: 기획 에이전트 (Concept Agent) - 타겟 독자 분석 및 스토리보드 컨셉 설정"""
    heritages = state["heritages"]
    steps = state.get("steps_log", [])
    print(f"[Guidebook Agent] Planning concept for heritages: {heritages}")
    
    llm = get_llm("gpt-4o-mini") # 서브태스크용 경량 모델
    concept_text = ""
    
    if llm:
        try:
            prompt = f"""
            지정된 세종시 문화유산 목록: {heritages}
            
            이 문화유산들을 연계하여 하나의 고품격 관광 가이드북을 만들기 위한 기획안을 수립해 주십시오.
            - 가이드북의 타겟 독자층 설정 (예: 가족, 외국인, 역사 애호가)
            - 전체 스토리보드의 핵심 컨셉 및 테마 명명
            - 각 유산별로 전달하고자 하는 기획 의도 및 테마 매칭
            """
            res = llm.invoke(prompt)
            concept_text = res.content.strip()
        except Exception as e:
            print(f"[Concept Agent] LLM invocation failed: {e}")
            
    if not concept_text:
        # Fallback Mock Planning
        concept_text = f"""[기획안] 세종의 숨결을 걷다
- 타겟 독자: 문화재의 숨은 역사적 정취를 조용히 음미하고 싶은 가족 및 개인 탐방객
- 핵심 컨셉: 조선 및 백제 왕조의 서사에서 발견하는 세종시 지정 유산의 비장미와 고요함
- 기획 의도: {', '.join(heritages)} 유산의 역사적 유래와 볼거리를 짜임새 있게 연결"""

    steps.append({"node": "concept_agent", "status": "1단계: 기획 에이전트(Concept) 컨셉 및 테마 기획 완료"})
    state["concept"] = concept_text
    state["steps_log"] = steps
    return state

def writer_agent_node(state: GuidebookState) -> GuidebookState:
    """2단계: 작성 에이전트 (Writer Agent) - 문화유산 스토리텔링 스토리 초안 작성"""
    heritages = state["heritages"]
    concept = state["concept"]
    steps = state["steps_log"]
    print(f"[Guidebook Agent] Writing draft for: {heritages}")
    
    llm = get_llm("gpt-4o")
    draft_text = ""
    
    if llm:
        try:
            prompt = f"""
            기획 에이전트의 가이드북 기획안:
            {concept}
            
            지정된 세종시 문화유산 목록: {heritages}
            
            위 기획 컨셉에 기반하여 각 문화유산에 얽힌 흥미로운 역사적 스토리텔링 초안(한글)을 상세히 작성해 주십시오.
            친근하고 감성적이면서도 고풍스러운 가이드북 말투(~입니다, ~였습니다)를 활용하십시오.
            """
            res = llm.invoke(prompt)
            draft_text = res.content.strip()
        except Exception as e:
            print(f"[Writer Agent] LLM invocation failed: {e}")
            
    if not draft_text:
        draft_text = ""
        for h in heritages:
            draft_text += f"\n### 🏛️ {h}의 숨겨진 이야기\n"
            draft_text += f"이 장소는 오랜 세월 세종특별자치시를 수놓은 대표 유산입니다. 고즈넉한 풍경 속에 서려 있는 선조들의 오랜 염원과 숨결을 간직하고 있습니다.\n"
            
    steps.append({"node": "writer_agent", "status": "2단계: 작성 에이전트(Writer) 한국어 스토리텔링 초안 완성"})
    state["draft"] = draft_text
    state["steps_log"] = steps
    return state

def editor_agent_node(state: GuidebookState) -> GuidebookState:
    """3단계: 편집 에이전트 (Editor Agent) - 가독성 향상, 서식 및 소제목 윤문 정비"""
    draft = state["draft"]
    concept = state["concept"]
    steps = state["steps_log"]
    print("[Guidebook Agent] Editing and polishing layout...")
    
    llm = get_llm("gpt-4o-mini")
    edited_text = ""
    
    if llm:
        try:
            prompt = f"""
            기획 컨셉:
            {concept}
            
            작성 에이전트가 쓴 스토리텔링 초안:
            {draft}
            
            가이드북 편집자로서 위 초안을 윤문 및 편집해 주십시오.
            - 중요 포인트에 이모지 추가
            - 각 유산별 핵심 요약 강조 블록 배치
            - 장소별 추천 방문 포인트 제시
            - 가독성이 극대화되도록 구조적 제목(h3, h4) 정리
            """
            res = llm.invoke(prompt)
            edited_text = res.content.strip()
        except Exception as e:
            print(f"[Editor Agent] LLM invocation failed: {e}")
            
    if not edited_text:
        edited_text = draft.replace("### ", "#### 📌 ").replace("이야기", "이야기와 감상 포인트")
        
    steps.append({"node": "editor_agent", "status": "3단계: 편집 에이전트(Editor) 마크다운 레이아웃 및 윤문 편집 완료"})
    state["edited"] = edited_text
    state["steps_log"] = steps
    return state

def translator_agent_node(state: GuidebookState) -> GuidebookState:
    """4단계: 번역 에이전트 (Translator Agent) - 글로벌 배포용 영어 번역본 생성"""
    edited = state["edited"]
    steps = state["steps_log"]
    print("[Guidebook Agent] Translating guidebook to English...")
    
    llm = get_llm("gpt-4o-mini")
    translated_text = ""
    
    if llm:
        try:
            prompt = f"""
            다음은 세종시 문화유산 관광 가이드북의 국문 편집본입니다:
            {edited}
            
            외국인 관광객들도 아름다운 정취를 이해할 수 있도록 위 텍스트를 자연스럽고 격조 높은 영어(English)로 번역해 주십시오.
            """
            res = llm.invoke(prompt)
            translated_text = res.content.strip()
        except Exception as e:
            print(f"[Translator Agent] LLM invocation failed: {e}")
            
    if not translated_text:
        translated_text = "\n### 🌐 English Summary\nThis guidebook introduces the designated cultural heritages of Sejong City. Explore the quiet trails where past history meets the future."
        
    steps.append({"node": "translator_agent", "status": "4단계: 번역 에이전트(Translator) 영문 가이드북 번역 완료"})
    state["translated"] = translated_text
    state["steps_log"] = steps
    return state

def formulate_guidebook_output_node(state: GuidebookState) -> GuidebookState:
    """종합 가이드북 리포트 최종 병합"""
    concept = state["concept"]
    korean = state["edited"]
    english = state["translated"]
    
    merged = f"""# 🗺️ 세종시 문화유산 스마트 가이드북 & 스토리보드

---

## 📋 [1단계: 기획 컨셉]
{concept}

---

## ✍️ [2단계 & 3단계: 국문 스토리 가이드]
{korean}

---

## 🌐 [4단계: 영문 번역 가이드]
{english}
"""
    state["final_output"] = merged
    return state

# 3. LangGraph 스토리보드 워크플로 구축 및 컴파일
builder = StateGraph(GuidebookState)

builder.add_node("concept_agent", concept_agent_node)
builder.add_node("writer_agent", writer_agent_node)
builder.add_node("editor_agent", editor_agent_node)
builder.add_node("translator_agent", translator_agent_node)
builder.add_node("formulate_output", formulate_guidebook_output_node)

builder.set_entry_point("concept_agent")
builder.add_edge("concept_agent", "writer_agent")
builder.add_edge("writer_agent", "editor_agent")
builder.add_edge("editor_agent", "translator_agent")
builder.add_edge("translator_agent", "formulate_output")
builder.add_edge("formulate_output", END)

guidebook_graph = builder.compile()

# 4. 엔드포인트 비즈니스 핸들러 함수
def run_guidebook_generation(heritages: List[str]) -> Dict[str, Any]:
    """선택된 문화유산 리스트를 이용해 4대 에이전트 스토리보드 실행"""
    initial_state = {
        "heritages": heritages,
        "concept": "",
        "draft": "",
        "edited": "",
        "translated": "",
        "final_output": "",
        "steps_log": []
    }
    
    output = guidebook_graph.invoke(initial_state)
    return {
        "status": "success",
        "heritages": heritages,
        "steps_log": output["steps_log"],
        "final_output": output["final_output"]
    }
