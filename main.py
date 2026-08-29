from langgraph.graph import StateGraph, START, END
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers.string import StrOutputParser
from typing_extensions import TypedDict
from typing import List
from dotenv import load_dotenv

from utils import save_state, get_outline, save_outline, load_state, format_messages_for_logging
from models import Task
from tools import retrieve, web_search, add_web_pages_json_to_croma  
from datetime import datetime
import os 

# 환경 변수 로드
load_dotenv()

# 현재 폴더 경로 찾기
# 랭그래프 이미지로 저장 및 추후 작업 결과 파일 저장 경로로 활용
filename = os.path.basename(__file__) # 현재 파일명 반환
absolute_path = os.path.abspath(__file__) # 현재 파일의 절대 경로 반환
current_path = os.path.dirname(absolute_path) # 현재 .py 파일이 있는 폴더 경로 

# 모델 초기화 (OpenAI 키가 있으면 gpt-4o 사용, 없으면 Gemini 모델로 대체)
openai_key = os.getenv("OPENAI_API_KEY")
if openai_key and openai_key != "your_openai_api_key_here":
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model="gpt-4o")
else:
    from langchain_google_genai import ChatGoogleGenerativeAI
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gemini_key or gemini_key == "your_gemini_api_key_here":
        gemini_key = "dummy_key_for_compilation"
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", api_key=gemini_key)
    print("[안내] 설정된 API Key가 없어 임시 키로 Gemini(gemini-1.5-flash) 모델을 구동합니다. 실제 가동 전 .env 파일을 설정해 주세요.")

# 검색 우선순위 설정 플래그
# False: 웹 검색 우선 수행 후 벡터 DB 검색 (현재 기본동작)
# True: 벡터 DB 우선 검색 후 정보 부족 시 웹 검색 수행 (추후 설정용)
PRIORITIZE_VECTOR_SEARCH = False

# 상태 정의
class State(TypedDict):
    messages: List[AnyMessage | str]
    task_history: List[Task]    
    references: dict

def supervisor(state: State): # supervisor 에이전트 추가
    print("\n\n============ SUPERVISOR ============")

    # 시스템 프롬프트 정의
    supervisor_system_prompt = PromptTemplate.from_template(
        """
        너는 AI 팀의 supervisor로서 AI 팀의 작업을 관리하고 지도한다.
        사용자가 원하는 책을 써야 한다는 최종 목표를 염두에 두고, 
        사용자의 요구를 달성하기 위해 현재 해야할 일이 무엇인지 결정한다.

        supervisor가 활용할 수 있는 agent는 다음과 같다.     
        - content_strategist: 사용자의 요구사항이 명확해졌을 때 사용한다. AI 팀의 콘텐츠 전략을 결정하고, 전체 책의 목차(outline)를 작성한다. 
        - communicator: AI 팀에서 해야 할 일을 스스로 판단할 수 없을 때 사용한다. 사용자에게 진행상황을 사용자에게 보고하고, 다음 지시를 물어본다. 
        - vector_search_agent: 벡터 DB 검색을 통해 목차(outline) 작성에 필요한 정보를 확보한다.
        - web_search_agent: 목차(outline) 작성 시 최신 정보나 벡터 DB의 기존 정보가 부족할 때 사용하며, 인터넷 검색을 통해 새로운 정보를 확보하여 벡터 DB에 추가한다.

        아래 내용을 고려하여, 현재 해야할 일이 무엇인지, 사용할 수 있는 agent를 단답으로 말하라.

        ------------------------------------------
        previous_outline: {outline}
        ------------------------------------------
        messages:
        {messages}
        """
    )

    # 체인 연결
    supervisor_chain = supervisor_system_prompt | llm.with_structured_output(Task)    

    # 메시지 가져오기
    messages = state.get("messages", [])		#⑤

    # inputs 설정
    inputs = {
        "messages": format_messages_for_logging(messages),
        "outline": get_outline(current_path)
    }

    # task 문자열로 생성
    task = supervisor_chain.invoke(inputs) 	#⑦
    task_history = state.get("task_history", [])    # 작업 이력 가져오기
    task_history.append(task)                    	# 작업 이력에 추가

   
    # 메시지 추가
    supervisor_message = AIMessage(f"[Supervisor] {task}")
    messages.append(supervisor_message)
    print(supervisor_message.content)

    # state 업데이트
    return {
        "messages": messages, 
        "task_history": task_history
    }

# supervisor's route
def supervisor_router(state: State):
    task = state['task_history'][-1]
    return task.agent			

def vector_search_agent(state: State):
    print("\n\n============ VECTOR SEARCH AGENT ============")
    
    tasks = state.get("task_history", [])
    task = tasks[-1]
    if task.agent != "vector_search_agent":
        raise ValueError(f"Vector Search Agent가 아닌 agent가 Vector Search Agent를 시도하고 있습니다.\n {task}")

    vector_search_system_prompt = PromptTemplate.from_template(
        """
        너는 다른 AI Agent 들이 수행한 작업을 바탕으로, 
        목차(outline) 작성에 필요한 정보를 벡터 검색을 통해 찾아내는 Agent이다.

        현재 목차(outline)을 작성하는데 필요한 정보를 확보하기 위해, 
        다음 내용을 활용해 적절한 벡터 검색을 수행하라. 

        - 검색 목적: {mission}
        --------------------------------
        - 과거 검색 내용: {references}
        --------------------------------
        - 이전 대화 내용: {messages}
        --------------------------------
        - 목차(outline): {outline}
        """
    )

    # inputs 설정
    mission = task.description
    references = state.get("references", {"queries": [], "docs": []})
    messages = state["messages"]
    outline = get_outline(current_path)

    inputs = {
        "mission": mission,
        "references": references,
        "messages": format_messages_for_logging(messages),
        "outline": outline
    }

    # LLM과 벡터 검색 모델 연결
    llm_with_retriever = llm.bind_tools([retrieve]) 
    vector_search_chain = vector_search_system_prompt | llm_with_retriever

    # LLM과 벡터 검색 모델 연결
    search_plans = vector_search_chain.invoke(inputs)
    # 검색할 내용 출력
    for tool_call in search_plans.tool_calls:
        print('-----------------------------------', tool_call)
        args = tool_call["args"]
       
        query = args["query"] 
        retrieved_docs = retrieve.invoke(args)
		#① (1) 결과 담아 두기
        references["queries"].append(query) 
        references["docs"] += retrieved_docs
    
    unique_docs = []
    unique_page_contents = set()

    for doc in references["docs"]:
        if doc.page_content not in unique_page_contents:
            unique_docs.append(doc)
            unique_page_contents.add(doc.page_content)
    references["docs"] = unique_docs

    # 검색 결과 출력 – 쿼리 출력
    print('Queries:--------------------------')
    queries = references["queries"]
    for query in queries:
        print(query)
    
    # 검색 결과 출력 – 문서 청크 출력
    print('References:--------------------------')
    for doc in references["docs"]:
        print(doc.page_content[:100])
        print('--------------------------')

    # task 완료
    tasks[-1].done = True
    tasks[-1].done_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 새로운 task 추가
    new_task = Task(
        agent="communicator",
        done=False,
        description="AI팀의 진행상황을 사용자에게 보고하고, 사용자의 의견을 파악하기 위한 대화를 나눈다",
        done_at=""
    )
    tasks.append(new_task)

    # vector search agent의 작업후기를 메시지로 생성
    msg_str = f"[VECTOR SEARCH AGENT] 다음 질문에 대한 검색 완료: {queries}"
    message = AIMessage(msg_str)
    print(msg_str)

    messages.append(message)
    # state 업데이트
    return {
        "messages": messages,
        "task_history": tasks,
        "references": references
    }

def vector_search_router(state: State):
    """
    vector_search_agent 이후 다음 단계를 결정하는 라우팅 함수.
    PRIORITIZE_VECTOR_SEARCH가 True일 때 벡터 DB에 정보가 부족하고 
    웹 검색이 아직 수행되지 않았다면 web_search_agent로 분기합니다.
    """
    if PRIORITIZE_VECTOR_SEARCH:
        web_search_done = any(t.agent == "web_search_agent" for t in state.get("task_history", []))
        if not web_search_done:
            references = state.get("references", {})
            docs = references.get("docs", [])
            # 검색 문서 수가 부족할 경우 (예: 2개 미만) 웹 검색을 보강하도록 분기
            if len(docs) < 2:
                tasks = state.get("task_history", [])
                new_task = Task(
                    agent="web_search_agent",
                    done=False,
                    description="벡터 DB 정보가 부족하여 웹 검색을 수행합니다.",
                    done_at=""
                )
                tasks.append(new_task)
                print("[Router] Vector DB search results are insufficient. Routing to web_search_agent.")
                return "web_search_agent"
                
    return "communicator"

def web_search_agent(state: State):
    print("\n\n============ WEB SEARCH AGENT ============")
    
    tasks = state.get("task_history", [])
    task = tasks[-1] if tasks else None
    
    if not task or task.agent != "web_search_agent":
        task = Task(
            agent="web_search_agent",
            done=False,
            description="인터넷 검색을 수행하여 부족한 정보를 보강합니다.",
            done_at=""
        )
        tasks.append(task)

    web_search_system_prompt = PromptTemplate.from_template(
        """
        너는 다른 AI Agent 들이 수행한 작업을 바탕으로, 
        목차(outline) 작성에 필요한 유용한 정보를 인터넷(웹) 검색을 통해 찾아내고
        그 검색 결과를 요약하여 벡터 DB에 저장하도록 돕는 Agent이다.

        현재 목차(outline)을 작성하는데 필요한 최신 정보나 부족한 정보를 확보하기 위해, 
        다음 내용을 활용해 적절한 웹 검색을 수행하라. 필요하다면 여러 번 검색 도구를 사용할 수 있다.

        - 검색 목적: {mission}
        --------------------------------
        - 과거 검색 내용: {references}
        --------------------------------
        - 이전 대화 내용: {messages}
        --------------------------------
        - 목차(outline): {outline}
        """
    )

    # inputs 설정
    mission = task.description
    references = state.get("references", {"queries": [], "docs": []})
    messages = state["messages"]
    outline = get_outline(current_path)

    inputs = {
        "mission": mission,
        "references": references,
        "messages": format_messages_for_logging(messages),
        "outline": outline
    }

    # LLM과 웹 검색 모델 연결
    llm_with_web_search = llm.bind_tools([web_search])
    web_search_chain = web_search_system_prompt | llm_with_web_search

    search_plans = web_search_chain.invoke(inputs)
    
    web_results = []
    
    if hasattr(search_plans, "tool_calls") and search_plans.tool_calls:
        for tool_call in search_plans.tool_calls:
            print('Web Search Tool Call:-----------------------------------', tool_call)
            args = tool_call["args"]
            query = args.get("query", "")
            if query:
                search_result = web_search.invoke(args)
                web_results.append({
                    "query": query,
                    "content": search_result
                })
    else:
        print("[INFO] No tool call generated by LLM for web search. Using mission as search query.")
        search_result = web_search.invoke({"query": mission})
        web_results.append({
            "query": mission,
            "content": search_result
        })

    # 검색 결과를 add_web_pages_json_to_croma 함수를 통해 벡터 DB에 저장
    if web_results:
        add_web_pages_json_to_croma(web_results)
        references["last_added_time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # task 완료
    task.done = True
    task.done_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 새로운 task 추가 (바로 vector_search_agent로 이어지도록 설정)
    new_task = Task(
        agent="vector_search_agent",
        done=False,
        description="웹 검색으로 추가된 최신 정보를 포함하여 벡터 DB에서 관련 문서를 다시 검색합니다",
        done_at=""
    )
    tasks.append(new_task)

    queries = [res["query"] for res in web_results]
    msg_str = f"[WEB SEARCH AGENT] 웹 검색 완료: {queries} (결과를 벡터 DB에 저장했습니다)"
    message = AIMessage(msg_str)
    print(msg_str)

    messages.append(message)
    # state 업데이트
    return {
        "messages": messages,
        "task_history": tasks,
        "references": references
    }


# 목차를 작성하는 노드(agent)
def content_strategist(state: State):
    print("\n\n============ CONTENT STRATEGIST ============")

    # 시스템 프롬프트 정의
    content_strategist_system_prompt = PromptTemplate.from_template(
        """
        너는 책을 쓰는 AI팀의 콘텐츠 전략가(Content Strategist)로서,
        이전 대화 내용을 바탕으로 사용자의 요구사항을 분석하고, AI팀이 쓸 책의 세부 목차를 결정한다.

        지난 목차가 있다면 그 버전을 사용자의 요구에 맞게 수정하고, 없다면 새로운 목차를 제안한다.

        --------------------------------
        - 지난 목차: {outline}
        --------------------------------
        - 이전 대화 내용: {messages}
        """
    )

    # 시스템 프롬프트와 모델을 연결
    content_strategist_chain = content_strategist_system_prompt | llm | StrOutputParser()

    messages = state["messages"]        # 상태에서 메시지를 가져옴
    outline = get_outline(current_path) # 저장된 목차를 가져옴

    # 입력값 정의
    inputs = {
        "messages": format_messages_for_logging(messages),
        "outline": outline
    }

    # 목차 작성
    gathered = ''
    for chunk in content_strategist_chain.stream(inputs):
        gathered += chunk
        print(chunk, end='')

    print()

    save_outline(current_path, gathered) # 목차 저장

    # 메시지 추가    
    content_strategist_message = f"[Content Strategist] 목차 작성 완료"
    print(content_strategist_message)
    messages.append(AIMessage(content_strategist_message))

    task_history = state.get("task_history", []) # task_history 가져오기
    # 최근 task 작업완료(done) 처리하기
    if task_history[-1].agent != "content_strategist": 
        raise ValueError(f"Content Strategist가 아닌 agent가 목차 작성을 시도하고 있습니다.\n {task_history[-1]}")
    
    task_history[-1].done = True
    task_history[-1].done_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 다음 작업이 communicator로 사용자와 대화하는 것이므로 새 작업 추가 
    new_task = Task(
        agent="communicator",
        done=False,
        description="AI팀의 진행상황을 사용자에게 보고하고, 사용자의 의견을 파악하기 위한 대화를 나눈다",
        done_at=""
    )
    task_history.append(new_task)

    print(new_task)

    # 현재 state를 업데이트한다. 
    return {
        "messages": messages,
        "task_history": task_history
    }


# 사용자와 대화할 노드(agent): communicator
def communicator(state: State):
    print("\n\n============ COMMUNICATOR ============")

    # 시스템 프롬프트 정의
    communicator_system_prompt = PromptTemplate.from_template(
        """
        너는 책을 쓰는 AI팀의 커뮤니케이터로서, 
        AI팀의 진행상황을 사용자에게 보고하고, 사용자의 의견을 파악하기 위한 대화를 나눈다. 

        사용자도 outline(목차)을 이미 보고 있으므로, 다시 출력할 필요는 없다.
        outline: {outline} 
        --------------------------------
        messages: {messages}
        """
    )

    #② 시스템 프롬프트와 모델을 연결
    system_chain = communicator_system_prompt | llm

    # 상태에서 메시지를 가져옴
    messages = state["messages"]

    # 입력값 정의
    inputs = {
        "messages": format_messages_for_logging(messages),
        "outline": get_outline(current_path)
    }

    # 스트림되는 메시지를 출력하면서, gathered에 모으기
    gathered = None

    print('\nAI\t: ', end='')
    for chunk in system_chain.stream(inputs):
        print(chunk.content, end='')

        if gathered is None:
            gathered = chunk
        else:
            gathered += chunk

    messages.append(gathered)

    task_history = state.get("task_history", []) 
    if task_history[-1].agent != "communicator":
        raise ValueError(f"Communicator가 아닌 agent가 대화를 시도하고 있습니다.\n {task_history[-1]}")
    
    task_history[-1].done = True
    task_history[-1].done_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    return {
        "messages": messages,
        "task_history": task_history
    }


from pydantic import BaseModel, Field

class RouteDecision(BaseModel):
    route: str = Field(description="어디로 갈지 경로 결정: 'casual' (일상 대화, 인사, 잡담, 안부 묻기 등) 또는 'rag' (책 내용, 목차 작성, 자료 검색, 전문 지식, 특정 문서 검색 등 RAG 시스템 검색이 필요한 질문)")

def route_question_node(state: State):
    print("\n\n============ QUESTION ROUTER ============")
    last_message = state["messages"][-1]
    last_msg_content = last_message.content if hasattr(last_message, "content") else str(last_message)
    
    router_prompt = PromptTemplate.from_template(
        """
        너는 사용자의 질문을 분류하는 분류 에이전트(Question Router)이다.
        아래 질문을 보고, 일상적인 대화(인사, 소개, 날씨, 잡담, 감정 표현 등)인지, 
        아니면 벡터 DB나 웹 검색(RAG)이 필요한 구체적인 정보 탐색/분석/지시 질문인지 분류하라.
        
        질문: {question}
        """
    )
    
    router_chain = router_prompt | llm.with_structured_output(RouteDecision)
    
    try:
        decision = router_chain.invoke({"question": last_msg_content})
        route = decision.route
    except Exception as e:
        print(f"[ERROR] Router failed: {e}. Defaulting to rag.")
        route = "rag"
        
    print(f"[Router Decision] Route choice: {route} (Question: '{last_msg_content}')")
    
    tasks = state.get("task_history", [])
    if route == "casual":
        tasks.append(Task(
            agent="communicator",
            done=False,
            description="일상 대화에 답변하고 사용자와 가벼운 대화를 나눕니다.",
            done_at=""
        ))
        
    references = state.get("references", {})
    references["next_agent"] = "communicator" if route == "casual" else "supervisor"
    
    return {
        "task_history": tasks,
        "references": references
    }

def start_router(state: State):
    """
    router 노드 이후 다음 단계를 결정하는 라우팅 함수.
    """
    next_agent = state.get("references", {}).get("next_agent", "supervisor")
    return next_agent

# 상태 그래프 정의
graph_builder = StateGraph(State)

# Nodes
graph_builder.add_node("router", route_question_node)
graph_builder.add_node("supervisor", supervisor)     
graph_builder.add_node("communicator", communicator)
graph_builder.add_node("content_strategist", content_strategist)
graph_builder.add_node("vector_search_agent", vector_search_agent)
graph_builder.add_node("web_search_agent", web_search_agent)

# Edges
graph_builder.add_edge(START, "router")
graph_builder.add_conditional_edges(
    "router",
    start_router,
    {
        "supervisor": "supervisor",
        "communicator": "communicator"
    }
)
graph_builder.add_conditional_edges(
    "supervisor", 
    supervisor_router,
    {
        "content_strategist": "content_strategist",
        "communicator": "communicator",
        "vector_search_agent": "vector_search_agent",
        "web_search_agent": "web_search_agent"
    }
)
graph_builder.add_edge("content_strategist", "communicator")
graph_builder.add_conditional_edges(
    "vector_search_agent",
    vector_search_router,
    {
        "communicator": "communicator",
        "web_search_agent": "web_search_agent"
    }
)
graph_builder.add_edge("web_search_agent", "vector_search_agent")
graph_builder.add_edge("communicator", END)

graph = graph_builder.compile()

# FastAPI 설정 (구글 클라우드 런 연동 및 API 대응용)
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="LangGraph Book Writer API",
    description="A FastAPI server running the book writer LangGraph agent team.",
    version="1.0.0"
)

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str
    db_row_count: int = 0
    last_added_time: str = "최근 추가 이력 없음"
    execution_time_sec: float = 0.0
    outline: str = ""

@app.get("/")
def read_root():
    outline = get_outline(current_path)
    db_row_count = 0
    try:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        if supabase_url and supabase_key and supabase_url != "your_supabase_url_here":
            from supabase import create_client
            supabase = create_client(supabase_url, supabase_key)
            res = supabase.table("documents").select("id", count="exact").limit(1).execute()
            db_row_count = res.count if res.count is not None else 0
    except Exception as e:
        print(f"[ERROR] Failed to fetch Supabase row count: {e}")
        
    return {
        "status": "running",
        "info": "LangGraph Book Writer API is ready!",
        "outline": outline,
        "db_row_count": db_row_count
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    import time
    start_time = time.time()

    # 기존에 저장된 상태 불러오기
    saved_state = load_state(current_path)
    
    if saved_state:
        initial_state = State(
            messages=saved_state["messages"],
            task_history=saved_state["task_history"],
            references=saved_state["references"]
        )
    else:
        # 최초 실행 시 초기 상태 구성
        initial_state = State(
            messages=[
                SystemMessage(
                    f"너희 AI들은 사용자의 요구에 맞는 책을 쓰는 작가팀이다. 사용자가 사용하는 언어로 대화하라. 현재시각은 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}이다."
                )
            ],
            task_history=[],
            references={"queries": [], "docs": [], "last_added_time": "최근 추가 이력 없음"}
        )
    
    # 새 사용자 메시지 추가
    initial_state["messages"].append(HumanMessage(content=request.message))
    
    try:
        # 동기적으로 실행되는 graph.invoke를 비동기 루프 상에서 실행
        import asyncio
        loop = asyncio.get_event_loop()
        final_state = await loop.run_in_executor(None, graph.invoke, initial_state)
        
        # 상태 기록 저장
        save_state(current_path, final_state)
        
        # 최종 AI(Communicator)의 답변 메시지 추출
        last_msg = final_state["messages"][-1]
        reply_content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        
        # 실행 시간 계산
        execution_time = round(time.time() - start_time, 2)
        
        # 마지막 추가 시간 추출
        last_added_time = final_state.get("references", {}).get("last_added_time", "최근 추가 이력 없음")
        
        # 벡터 DB 행 수 조회
        db_row_count = 0
        try:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_KEY")
            if supabase_url and supabase_key and supabase_url != "your_supabase_url_here":
                from supabase import create_client
                supabase = create_client(supabase_url, supabase_key)
                res = supabase.table("documents").select("id", count="exact").limit(1).execute()
                db_row_count = res.count if res.count is not None else 0
        except Exception as e:
            print(f"[ERROR] Failed to fetch Supabase row count: {e}")
            
        # 마지막 목차 읽어오기
        outline = get_outline(current_path)
        
        return ChatResponse(
            reply=reply_content,
            db_row_count=db_row_count,
            last_added_time=last_added_time,
            execution_time_sec=execution_time,
            outline=outline
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error executing agent workflow: {str(e)}"
        )

# 로컬 단독 터미널 실행 대응 (__name__ == "__main__" 시 CLI 모드로 구동)
if __name__ == "__main__":
    # Mermaid 그래프 이미지 생성 시도 (네트워크 환경에 따라 차단되거나 실패할 수 있으므로 예외처리)
    try:
        graph.get_graph().draw_mermaid_png(output_file_path=absolute_path.replace('.py', '.png'))
    except Exception as e:
        print(f"[안내] Mermaid 그래프 이미지 생성 실패 (가벼운 경고): {e}")

    # 상태 초기화
    state = State(
        messages = [
            SystemMessage(
                    f"""
                너희 AI들은 사용자의 요구에 맞는 책을 쓰는 작가팀이다.
                사용자가 사용하는 언어로 대화하라.
    
                현재시각은 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}이다.
    
                """
            )
        ],
        task_history=[]
    )
    
    print("\n--- CLI 대화 모드로 구동합니다. 종료하려면 'exit'을 입력하세요. ---")
    while True:
        user_input = input("\nUser\t: ").strip()
    
        if user_input.lower() in ['exit', 'quit', 'q']:
            print("Goodbye!")
            break
        
        state["messages"].append(HumanMessage(user_input))
        state = graph.invoke(state)
    
        print('\n------------------------------------ MESSAGE COUNT\t', len(state["messages"]))
    
        save_state(current_path, state) # 현재 state 내용 저장