import os
import uuid
from typing import List, Dict, Any, Annotated, TypedDict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# LangChain & LangGraph Imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

# Load environment variables
dotenv_path = r"C:\Anti-project\.env"
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    load_dotenv()

# Initialize FastAPI
app = FastAPI(
    title="LangGraph AI Agent",
    description="Recipe AI Agent with LangGraph workflow, checkpointer state persistence, and Human-in-the-Loop approval.",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper function to initialize LLM based on user selection
def get_llm(model_name: str):
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if model_name == "openai":
        if not openai_key or "your_openai_api_key" in openai_key:
            raise HTTPException(status_code=400, detail="OpenAI API Key is not properly configured on the server.")
        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=openai_key,
            temperature=0.3
        )
    else:
        # Default to Gemini
        if not gemini_key or "your_gemini_api_key" in gemini_key:
            # Fallback to OpenAI if Gemini is not set and OpenAI is set
            if openai_key and "your_openai_api_key" not in openai_key:
                return ChatOpenAI(
                    model="gpt-4o-mini",
                    api_key=openai_key,
                    temperature=0.3
                )
            raise HTTPException(status_code=400, detail="Gemini API Key is not properly configured on the server.")
        return ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=gemini_key,
            temperature=0.3
        )

# Mock Recipes for robust fallbacks
def get_mock_recipe(query: str, section: str) -> str:
    if "떡볶이" in query:
        if section == "ingredients":
            return "- 떡볶이 떡 300g\n- 사각 어묵 2장\n- 대파 1/2대\n- 고추장 2큰술\n- 고춧가루 1큰술\n- 설탕 2큰술\n- 진간장 1큰술\n- 물 400ml"
        elif section == "steps":
            return "1. 떡볶이 떡은 물에 헹구어 건져둡니다.\n2. 어묵과 대파는 먹기 좋은 크기로 썹니다.\n3. 냄비에 물과 고추장, 고춧가루, 설탕, 간장을 넣고 풉니다.\n4. 물이 끓으면 떡과 어묵을 넣고 국물이 걸쭉해질 때까지 조립니다.\n5. 마지막에 대파를 넣고 한소끔 더 끓여 완성합니다."
        else:
            return "- 떡이 딱딱하다면 물에 10분 정도 미리 불려 두면 훨씬 말랑하고 쫄깃해집니다.\n- 기호에 따라 삶은 계란이나 양배추, 라면 사리 등을 추가하면 더욱 맛있습니다."
    elif "김치찌개" in query:
        if section == "ingredients":
            return "- 잘 익은 김치 1/4포기\n- 돼지고기(찌개용) 200g\n- 두부 1/2모\n- 대파 1/2대\n- 다진 마늘 1큰술\n- 고춧가루 1큰술\n- 국간장 1큰술\n- 쌀뜨물 또는 물 500ml"
        elif section == "steps":
            return "1. 김치와 돼지고기는 한입 크기로 썰고, 두부와 대파도 썰어 둡니다.\n2. 냄비에 돼지고기와 김치를 함께 넣고 고기 겉면이 익을 때까지 달달 볶아줍니다.\n3. 쌀뜨물을 붓고 강불에서 끓이다가 끓어오르면 중불로 줄여 15분 이상 푹 끓입니다.\n4. 다진 마늘, 고춧가루, 국간장으로 양념을 하고 두부를 넣습니다.\n5. 대파를 올린 후 2-3분간 더 끓여 마무리합니다."
        else:
            return "- 신김치를 사용해야 깊은 맛이 납니다. 너무 신 김치라면 설탕을 1/2작은술 넣으면 신맛이 잡힙니다.\n- 육수로 쌀뜨물을 사용하면 찌개의 국물이 훨씬 구수하고 깊어집니다."
    else:
        if section == "ingredients":
            return f"- {query} 주재료\n- 소금, 후추, 참기름 등 기본 양념 채소"
        elif section == "steps":
            return f"1. {query} 주재료를 씻고 손질합니다.\n2. 달궈진 냄비/팬에 재료를 넣고 볶거나 조리합니다.\n3. 간을 보고 마지막에 대파나 양념을 얹어 완성합니다."
        else:
            return f"- {query} 조리 시 불 조절에 주의하세요.\n- 신선한 제철 재료를 사용하면 더욱 풍미가 살아납니다."

# Define Recommand Recipe Tool
@tool
def recommand_recipe(query: str, section: str) -> str:
    """사용자가 요청한 요리의 레시피를 제공합니다.
    query: 요리 이름 (예: 떡볶이, 김치찌개 등)
    section: 작성할 항목 ('ingredients' (재료 목록), 'steps' (조리 순서), 'tips' (팁/주의사항))
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if (not gemini_key or "your_gemini" in gemini_key) and (not openai_key or "your_openai" in openai_key):
        return get_mock_recipe(query, section)
        
    try:
        # Determine active key to perform tool execution
        if gemini_key and "your_gemini" not in gemini_key:
            llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=gemini_key)
        else:
            llm = ChatOpenAI(model="gpt-4o-mini", api_key=openai_key)
            
        sec_name = {"ingredients": "재료 목록", "steps": "조리 순서", "tips": "팁 및 주의사항"}.get(section, section)
        prompt = (
            f"요리 '{query}'의 {sec_name}에 대한 핵심 정보를 제공하세요.\n"
            f"이 정보는 최종 답변이 아닌 초안으로 사용될 것이므로, "
            f"쓸데없는 설명이나 인사말 없이 해당되는 정보(원재료 목록이나 순서)만 불릿포인트 혹은 번호 매기기 형태로 깔끔하고 간결하게 텍스트만 작성해 주세요."
        )
        res = llm.invoke(prompt)
        return res.content.strip()
    except Exception as e:
        print(f"Tool execution failed: {e}. Using mock data fallback.")
        return get_mock_recipe(query, section)

# LangGraph State Definition
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    recipe_query: str
    selected_sections: List[str]
    recipe_draft: Dict[str, str]
    recipe_final: Dict[str, str]
    feedback: str
    approved: bool
    model: str

# Define Node: planning and invoking the tool
def plan_node(state: AgentState):
    query = state["recipe_query"]
    sections = state["selected_sections"]
    draft = state.get("recipe_draft", {}) or {}
    
    # Process requested sections through our tool
    for sec in sections:
        if sec not in draft or not draft[sec]:
            tool_output = recommand_recipe.invoke({"query": query, "section": sec})
            draft[sec] = tool_output
            
    messages = list(state.get("messages", []))
    messages.append(("assistant", f"요리 '{query}'의 각 항목 초안 정보를 수집했습니다."))
    
    return {
        "recipe_draft": draft,
        "messages": messages
    }

# Define Node: compilation draft state
def draft_node(state: AgentState):
    # This node simply passes the state forward and serves as a check-in point
    messages = list(state.get("messages", []))
    messages.append(("assistant", "사용자 검토를 위한 초안이 준비되었습니다."))
    return {"messages": messages}

# Define Node: human approval node (Breakpoint placeholder)
def approval_node(state: AgentState):
    # Execution halts BEFORE this node. When resumed, this node receives updated status.
    return state

# Define Node: revision based on user feedback
def revise_node(state: AgentState):
    query = state["recipe_query"]
    draft = state.get("recipe_draft", {}) or {}
    feedback = state.get("feedback", "")
    model_name = state.get("model", "gemini")
    
    llm = get_llm(model_name)
    revised_draft = {}
    
    for sec, content in draft.items():
        sec_name = {"ingredients": "재료 목록", "steps": "조리 순서", "tips": "팁 및 주의사항"}.get(sec, sec)
        prompt = (
            f"요리 '{query}'의 레시피 {sec_name} 초안입니다:\n"
            f"====================\n"
            f"{content}\n"
            f"====================\n\n"
            f"사용자 피드백: {feedback}\n\n"
            f"사용자의 피드백을 반영하여 초안 내용을 정밀하게 수정 및 변경해 주세요. 다른 인사말은 절대 포함하지 마세요."
        )
        try:
            res = llm.invoke(prompt)
            revised_draft[sec] = res.content.strip()
        except Exception as e:
            print(f"Revision error on {sec}: {e}")
            revised_draft[sec] = content + f"\n(수정 실패 - 피드백 미반영: {feedback})"

    messages = list(state.get("messages", []))
    messages.append(("user", f"피드백 제출: {feedback}"))
    messages.append(("assistant", "피드백을 반영하여 요리 레시피 초안을 업데이트했습니다."))
    
    return {
        "recipe_draft": revised_draft,
        "feedback": "",  # Clear feedback after applying
        "messages": messages
    }

# Define Node: finalize the recipe formatting
def finalize_node(state: AgentState):
    query = state["recipe_query"]
    draft = state.get("recipe_draft", {})
    model_name = state.get("model", "gemini")
    
    llm = get_llm(model_name)
    final_output = {}
    
    for sec, content in draft.items():
        sec_name = {"ingredients": "재료 목록", "steps": "조리 순서", "tips": "팁 및 주의사항"}.get(sec, sec)
        prompt = (
            f"요리 '{query}'의 {sec_name}에 대한 최종 컴파일 단계입니다.\n"
            f"다음 초안 내용을 가독성이 뛰어나고 전문적인 마크다운 형식(소제목 및 글머리 기호 사용)으로 정밀하게 교정 및 보완해서 작성해 주세요.\n\n"
            f"초안 내용:\n{content}"
        )
        try:
            res = llm.invoke(prompt)
            final_output[sec] = res.content.strip()
        except Exception as e:
            print(f"Finalization error on {sec}: {e}")
            final_output[sec] = content

    messages = list(state.get("messages", []))
    messages.append(("assistant", "최종 레시피가 성공적으로 생성 및 가공되었습니다!"))
    
    return {
        "recipe_final": final_output,
        "messages": messages
    }

# Conditional routing edge function
def route_after_approval(state: AgentState):
    if state.get("approved"):
        return "finalize_node"
    else:
        return "revise_node"

# Construct state graph
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("plan_node", plan_node)
workflow.add_node("draft_node", draft_node)
workflow.add_node("approval_node", approval_node)
workflow.add_node("revise_node", revise_node)
workflow.add_node("finalize_node", finalize_node)

# Add edges
workflow.set_entry_point("plan_node")
workflow.add_edge("plan_node", "draft_node")
workflow.add_edge("draft_node", "approval_node")

# Conditional edges from approval node
workflow.add_conditional_edges(
    "approval_node",
    route_after_approval,
    {
        "finalize_node": "finalize_node",
        "revise_node": "revise_node"
    }
)

# Loops from revise back to draft compilation
workflow.add_edge("revise_node", "draft_node")
workflow.add_edge("finalize_node", END)

# Compile graph with memory saver and approval node breakpoint
memory = MemorySaver()
app_graph = workflow.compile(
    checkpointer=memory,
    interrupt_before=["approval_node"]
)

# API Schemas
class StartRequest(BaseModel):
    query: str
    sections: List[str]
    model: str

class ApproveRequest(BaseModel):
    thread_id: str
    approved: bool
    feedback: str = ""

@app.get("/")
def read_root():
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    return {
        "status": "healthy",
        "title": "LangGraph AI Agent Server",
        "gemini_configured": bool(gemini_key and "your_gemini" not in gemini_key),
        "openai_configured": bool(openai_key and "your_openai" not in openai_key)
    }

@app.post("/agent/start")
def start_agent(payload: StartRequest):
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    if not payload.sections:
        raise HTTPException(status_code=400, detail="At least one section must be selected.")
        
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    # Run the graph until the interrupt breakpoint
    try:
        app_graph.invoke({
            "recipe_query": payload.query,
            "selected_sections": payload.sections,
            "recipe_draft": {},
            "recipe_final": {},
            "feedback": "",
            "approved": False,
            "model": payload.model,
            "messages": [("user", f"레시피 요청: {payload.query}")]
        }, config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph execution error: {str(e)}")
        
    # Retrieve state values
    state_info = app_graph.get_state(config)
    next_nodes = state_info.next
    
    status = "pending_approval" if "approval_node" in next_nodes else "completed"
    
    # Render Mermaid graph description
    try:
        mermaid_markup = app_graph.get_graph().draw_mermaid()
    except Exception:
        mermaid_markup = ""
        
    return {
        "thread_id": thread_id,
        "status": status,
        "recipe_draft": state_info.values.get("recipe_draft", {}),
        "recipe_final": state_info.values.get("recipe_final", {}),
        "messages": [
            {"role": "user" if m.type == "human" else "assistant", "content": m.content}
            for m in state_info.values.get("messages", [])
        ],
        "mermaid": mermaid_markup
    }

@app.post("/agent/approve")
def approve_agent(payload: ApproveRequest):
    config = {"configurable": {"thread_id": payload.thread_id}}
    
    state_info = app_graph.get_state(config)
    if not state_info.values:
        raise HTTPException(status_code=404, detail="Thread not found or expired.")
        
    # Update graph state with user choice
    app_graph.update_state(
        config,
        {"approved": payload.approved, "feedback": payload.feedback},
        as_node="approval_node"
    )
    
    # Resume graph execution
    try:
        app_graph.invoke(None, config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resuming graph execution error: {str(e)}")
        
    # Retrieve updated state values
    updated_state_info = app_graph.get_state(config)
    next_nodes = updated_state_info.next
    
    status = "pending_approval" if "approval_node" in next_nodes else "completed"
    
    try:
        mermaid_markup = app_graph.get_graph().draw_mermaid()
    except Exception:
        mermaid_markup = ""
        
    return {
        "thread_id": payload.thread_id,
        "status": status,
        "recipe_draft": updated_state_info.values.get("recipe_draft", {}),
        "recipe_final": updated_state_info.values.get("recipe_final", {}),
        "messages": [
            {"role": "user" if m.type == "human" else "assistant", "content": m.content}
            for m in updated_state_info.values.get("messages", [])
        ],
        "mermaid": mermaid_markup
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
