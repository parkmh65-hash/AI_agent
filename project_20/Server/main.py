import os
import uuid
from typing import List, Dict, Any, Annotated, TypedDict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# LangChain & LangGraph Imports
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import ToolMessage, AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

# CrewAI Imports
from crewai import Agent, Task, Crew

# Load environment variables
dotenv_path = r"C:\Anti-project\.env"
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    load_dotenv()

# Initialize FastAPI
app = FastAPI(
    title="Multi Agent",
    description="Multi-Agent system using CrewAI, LangGraph, and Supabase Vector DB with query rewriting and Human-in-the-Loop approval.",
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

# Supabase Client Initialization
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase_client = None

if supabase_url and supabase_key and supabase_url != "your_supabase_url_here":
    try:
        from supabase import create_client
        supabase_client = create_client(supabase_url, supabase_key)
    except Exception as e:
        print(f"Failed to initialize Supabase client: {e}")

# Helper to get the correct LLM based on user selection and availability
def get_llm(model_name: str, temperature: float = 0.3):
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    is_gemini_valid = gemini_key and "your_gemini_api" not in gemini_key
    is_openai_valid = openai_key and "your_openai_api" not in openai_key
    
    if model_name == "ollama":
        try:
            # We attempt to use ChatOllama from langchain_community
            from langchain_community.chat_models import ChatOllama
            print("Initializing local Ollama Llama3 model...")
            return ChatOllama(
                model="llama3", 
                base_url="http://localhost:11434", 
                temperature=temperature
            )
        except Exception as e:
            print(f"Failed to load Ollama ({e}). Falling back to OpenAI/Gemini.")
            model_name = "openai" if is_openai_valid else "gemini"

    if model_name == "gemini":
        if is_gemini_valid:
            return ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=gemini_key,
                temperature=temperature
            )
        elif is_openai_valid:
            print("Gemini key is placeholder, falling back to OpenAI")
            return ChatOpenAI(
                model="gpt-4o-mini",
                api_key=openai_key,
                temperature=temperature
            )
        else:
            raise HTTPException(status_code=400, detail="No valid LLM credentials found on the server.")
    else:
        # Default to OpenAI
        if is_openai_valid:
            return ChatOpenAI(
                model="gpt-4o-mini",
                api_key=openai_key,
                temperature=temperature
            )
        elif is_gemini_valid:
            print("OpenAI key is placeholder, falling back to Gemini")
            return ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=gemini_key,
                temperature=temperature
            )
        else:
            raise HTTPException(status_code=400, detail="No valid LLM credentials found on the server.")

# Helper to get the correct CrewAI LLM (Native LLM wraps to avoid Pydantic validation conflicts)
def get_crewai_llm(model_name: str, temperature: float = 0.3):
    from crewai import LLM
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    is_gemini_valid = gemini_key and "your_gemini_api" not in gemini_key
    is_openai_valid = openai_key and "your_openai_api" not in openai_key
    
    if model_name == "ollama":
        print("Using CrewAI LLM for local Ollama Llama3 model...")
        return LLM(
            model="ollama/llama3",
            base_url="http://localhost:11434",
            temperature=temperature
        )
        
    if model_name == "gemini":
        if is_gemini_valid:
            return LLM(
                model="gemini/gemini-1.5-flash",
                api_key=gemini_key,
                temperature=temperature
            )
        elif is_openai_valid:
            print("Gemini key is placeholder, falling back to OpenAI in CrewAI")
            return LLM(
                model="gpt-4o-mini",
                api_key=openai_key,
                temperature=temperature
            )
        else:
            raise HTTPException(status_code=400, detail="No valid LLM credentials found on the server.")
    else:
        # Default to OpenAI
        if is_openai_valid:
            return LLM(
                model="gpt-4o-mini",
                api_key=openai_key,
                temperature=temperature
            )
        elif is_gemini_valid:
            print("OpenAI key is placeholder, falling back to Gemini in CrewAI")
            return LLM(
                model="gemini/gemini-1.5-flash",
                api_key=gemini_key,
                temperature=temperature
            )
        else:
            raise HTTPException(status_code=400, detail="No valid LLM credentials found on the server.")

# Helper to get the correct embeddings model
def get_embeddings():
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    is_openai_valid = openai_key and "your_openai_api" not in openai_key
    is_gemini_valid = gemini_key and "your_gemini_api" not in gemini_key
    
    if is_openai_valid:
        return OpenAIEmbeddings(model="text-embedding-3-small", api_key=openai_key)
    elif is_gemini_valid:
        base_embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=gemini_key)
        class PaddedEmbeddings:
            def embed_documents(self, texts):
                vecs = base_embeddings.embed_documents(texts)
                return [v + [0.0] * (1536 - len(v)) for v in vecs]
            def embed_query(self, text):
                v = base_embeddings.embed_query(text)
                return v + [0.0] * (1536 - len(v))
        return PaddedEmbeddings()
    else:
        class DummyEmbeddings:
            def embed_documents(self, texts):
                return [[0.0] * 1536 for _ in texts]
            def embed_query(self, text):
                return [0.0] * 1536
        return DummyEmbeddings()

# Mock Financial & Tech Data for RAG Fallbacks
MOCK_ARTICLES = [
    {
        "title": "인공지능 트렌드 2026 및 다중 에이전트 시스템(CrewAI)의 비즈니스 혁신",
        "url": "https://techblog.naver.com/ai_trend_2026",
        "content": "2026년 인공지능 분야의 핵심 화두는 단일 거대모델(LLM)을 넘어 여러 전문 에이전트가 협업하는 '다중 에이전트 시스템(Multi-Agent System)'입니다. 기획, 작성, 편집, 번역에 이르는 비즈니스 문서 자동화가 대표적인 적용 사례입니다. CrewAI와 같은 프레임워크는 각각의 에이전트에 고유한 목표(Goal)와 역할극(Roleplay) 백스토리를 주어 자율적으로 업무를 조율하게 만듭니다. 이러한 구조는 작업 완성도를 비약적으로 높이며 단순 반복적인 업무 프로세스를 90% 이상 자동화하는 성과를 보이고 있습니다."
    },
    {
        "title": "LangGraph와 Human-in-the-Loop 패턴을 활용한 신뢰성 높은 AI 서비스 구축",
        "url": "https://techblog.yahoo.com/langgraph_human_in_the_loop",
        "content": "LangGraph는 상태(State)와 순환 흐름을 가진 AI 워크플로를 구축하는 데 있어 압도적인 유연성을 제공합니다. 특히 중요 의사결정 시점에 사람의 개입을 허용하는 'Human-in-the-Loop' 패턴을 완벽히 지원합니다. 그래프 실행 도중 중단점(Breakpoint)을 설정하여, AI가 수집한 데이터와 쿼리를 검증하고 사용자의 피드백을 반영해 작업을 다시 이어갈 수 있습니다. 이는 RAG(검색 증강 생성) 시스템에서 무작위성으로 발생할 수 있는 환각 현상을 억제하고 데이터 신뢰성을 보장하는 데 결정적인 역할을 수행합니다."
    },
    {
        "title": "클라우드 런(Cloud Run)과 수파베이스(Supabase) 벡터스토어를 활용한 서버리스 AI 배포",
        "url": "https://techblog.daum.net/cloudrun_supabase_rag",
        "content": "구글 클라우드 런(Google Cloud Run)은 컨테이너화된 웹 서비스를 완전 서버리스 형태로 확장할 수 있게 해줍니다. 여기에 수파베이스(Supabase)의 pgvector 확장을 벡터데이터베이스로 결합하면, 저비용 고효율 RAG 인프라를 가동할 수 있습니다. 텍스트 임베딩 모델을 통해 문서를 벡터화한 후 Supabase에 저장하고, 유사도 매칭 RPC(match_documents) 함수를 호출하여 필요한 컨텍스트를 신속하게 조회할 수 있습니다. 로컬 개발 환경과 배포 환경의 설정을 동일하게 구성하여 이식성을 보장하는 것이 핵심입니다."
    }
]

# Database Seed Endpoint
@app.post("/db/seed")
def seed_database():
    if not supabase_client:
        raise HTTPException(
            status_code=400,
            detail="Supabase is not configured. Please set SUPABASE_URL and SUPABASE_KEY in .env."
        )
    
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import SupabaseVectorStore
    from langchain_core.documents import Document
    
    docs = []
    print("Preparing documents for database seeding...")
    for article in MOCK_ARTICLES:
        docs.append(
            Document(
                page_content=article["content"],
                metadata={"title": article["title"], "source": article["url"]}
            )
        )
        
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    chunks = text_splitter.split_documents(docs)
    
    try:
        embeddings = get_embeddings()
        SupabaseVectorStore.from_documents(
            documents=chunks,
            embedding=embeddings,
            client=supabase_client,
            table_name="documents",
            query_name="match_documents"
        )
        return {
            "status": "success",
            "message": f"Successfully ingested {len(chunks)} chunks into Supabase Vector Store."
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save to Supabase: {str(e)}."
        )

# Retrieval Search Function
def perform_retrieval(query: str) -> List[Any]:
    if not supabase_client:
        print("[WARNING] Supabase not initialized. Using local mock data search.")
        query_words = query.split()
        hits = []
        for article in MOCK_ARTICLES:
            score = sum(1 for w in query_words if w in article["content"] or w in article["title"])
            if score > 0:
                # Mock dynamic document representation
                class MockDoc:
                    def __init__(self, content, source):
                        self.page_content = content
                        self.metadata = {"source": source}
                hits.append(MockDoc(article["content"], article["url"]))
        return hits[:3] if hits else [
            type('MockDoc', (object,), {"page_content": "검색 결과를 찾을 수 없으며 Supabase 연동이 구성되지 않았습니다.", "metadata": {"source": "mock"}})()
        ]
        
    try:
        embeddings = get_embeddings()
        query_vec = embeddings.embed_query(query)
        
        res = supabase_client.rpc(
            "match_documents",
            {
                "query_embedding": query_vec,
                "match_threshold": 0.1,
                "match_count": 3
            }
        ).execute()
        
        docs = []
        for row in res.data:
            class DBDoc:
                def __init__(self, content, source):
                    self.page_content = content
                    self.metadata = {"source": source}
            docs.append(DBDoc(row.get("content", ""), row.get("source", row.get("metadata", {}).get("source", "unknown"))))
        return docs
    except Exception as e:
        print(f"Error querying vector store: {e}")
        class ErrorDoc:
            def __init__(self, content):
                self.page_content = content
                self.metadata = {"source": "error"}
        return [ErrorDoc(f"Supabase 검색 중 오류가 발생했습니다: {str(e)}")]

# Define LangGraph State
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    query: str
    current_query: str
    retrieved_documents: List[Any]
    approved: bool
    feedback: str
    model: str
    loop_step: int
    planner_output: str
    writer_output: str
    editor_output: str
    translation_output: str

# Node 1: Rewrite Query
def rewrite_node(state: AgentState):
    query = state["current_query"]
    feedback = state.get("feedback", "")
    
    prompt = (
        f"당신은 검색 최적화 에이전트입니다. 원본 주제: '{query}'\n"
        f"사용자 피드백: '{feedback}'\n"
        f"위 피드백을 반영하여 Supabase 벡터 DB 검색이 원활하도록 다듬어진 최적의 검색어 한 줄만(부가 설명 없이) 출력하세요."
    )
    llm = get_llm(state["model"])
    try:
        res = llm.invoke(prompt)
        rewritten = res.content.strip().strip('"').strip("'")
    except Exception as e:
        print(f"Query rewriting failed: {e}")
        rewritten = query
        
    return {
        "current_query": rewritten,
        "loop_step": state.get("loop_step", 0) + 1
    }

# Node 2: Retrieve from Supabase Vector Store
def retrieve_node(state: AgentState):
    query = state["current_query"]
    print(f"Running retrieval for query: {query}")
    docs = perform_retrieval(query)
    
    # Store documents list in state
    serialized_docs = [{"content": d.page_content, "source": d.metadata.get("source", "unknown")} for d in docs]
    
    return {
        "retrieved_documents": serialized_docs
    }

# Node 3: Placeholder node for Approval Breakpoint
def approval_node(state: AgentState):
    return {}

# Node 4: CrewAI Multi-Agent execution
def crew_node(state: AgentState):
    topic = state["query"]
    docs = state.get("retrieved_documents", [])
    context_str = "\n\n".join([f"Source: {d['source']}\nContent: {d['content']}" for d in docs])
    
    llm = get_crewai_llm(state["model"])
    
    print(f"Initializing CrewAI with model: {state['model']} for topic: {topic}")
    
    # Define Agents
    planner = Agent(
        role="Content Planner",
        goal=f"Draft a comprehensive blog post plan for the topic: {{topic}}",
        backstory="You are an expert content planner. You specialize in analyzing topics and writing structural, detailed, and search-optimized blog outlines.",
        llm=llm,
        allow_delegation=False,
        verbose=True
    )
    
    writer = Agent(
        role="Content Writer",
        goal="Write an opinionated and engaging blog post about the topic: {topic}",
        backstory="You are a professional content writer. You use structured plans and background context to write captivating opinion pieces for blogs.",
        llm=llm,
        allow_delegation=False,
        verbose=True
    )
    
    editor = Agent(
        role="Content Editor",
        goal="Review and edit the written blog post to optimize quality and readability",
        backstory="You are a meticulous content editor. You polish drafts, correct grammar mistakes, and refine styling to match industry standards.",
        llm=llm,
        allow_delegation=False,
        verbose=True
    )
    
    translate_writer = Agent(
        role="Korean Translator",
        goal="Translate the blog post accurately and naturally into Korean",
        backstory="You are a native Korean translator. You analyze the context, detect languages, and provide smooth Korean translations while preserving formatting.",
        memory=True,
        llm=llm,
        allow_delegation=False,
        verbose=True
    )
    
    # Define Tasks
    planning_task = Task(
        description=f"Analyze the topic: '{{topic}}' and the following retrieved background documents:\n{context_str}\n\nDraft a structured blog plan containing headings, key talking points, and targeted SEO elements.",
        expected_output="A structured blog outline in markdown format.",
        agent=planner
    )
    
    writing_task = Task(
        description="Using the content plan generated, write an engaging and informative blog post. Make sure to capture a professional opinion style and cite retrieved facts naturally.",
        expected_output="A full-length blog post draft in markdown format.",
        agent=writer
    )
    
    editing_task = Task(
        description="Polish the draft blog post. Improve tone consistency, fix spelling errors, and verify markdown layout formatting.",
        expected_output="An edited, high-quality blog post in markdown format.",
        agent=editor
    )
    
    translate_task = Task(
        description="Translate the edited blog post into Korean. Maintain a warm, clear tone suitable for business and tech readers. Ensure markdown formatting is intact.",
        expected_output="A polished Korean version of the blog post in markdown.",
        agent=translate_writer,
        async_execution=False,
        output_file="translate-blog.md"
    )
    
    # Assemble and run Crew
    crew = Crew(
        agents=[planner, writer, editor, translate_writer],
        tasks=[planning_task, writing_task, editing_task, translate_task],
        verbose=True
    )
    
    try:
        # Launch CrewAI workflow
        crew_result = crew.kickoff(inputs={"topic": topic})
        raw_result = str(crew_result)
    except Exception as e:
        print(f"CrewAI execution failed: {e}")
        raw_result = f"CrewAI execution failed: {str(e)}"
        
    # Retrieve outputs
    p_out = planning_task.output.raw if planning_task.output else "기획안 생성 실패"
    w_out = writing_task.output.raw if writing_task.output else "초고 작성 실패"
    e_out = editing_task.output.raw if editing_task.output else "편집안 생성 실패"
    
    # Read output file if exists
    t_out = ""
    if os.path.exists("translate-blog.md"):
        try:
            with open("translate-blog.md", "r", encoding="utf-8") as f:
                t_out = f.read()
        except Exception as file_err:
            print(f"Failed to read translate-blog.md: {file_err}")
            
    if not t_out:
        t_out = translate_task.output.raw if translate_task.output else raw_result
        
    return {
        "planner_output": p_out,
        "writer_output": w_out,
        "editor_output": e_out,
        "translation_output": t_out
    }

# Routing logic after approval breakpoint
def route_after_approval(state: AgentState):
    if state.get("approved"):
        return "crew_node"
    else:
        return "rewrite_node"

# Set up LangGraph StateGraph
workflow = StateGraph(AgentState)

workflow.add_node("rewrite_node", rewrite_node)
workflow.add_node("retrieve_node", retrieve_node)
workflow.add_node("approval_node", approval_node)
workflow.add_node("crew_node", crew_node)

workflow.set_entry_point("rewrite_node")
workflow.add_edge("rewrite_node", "retrieve_node")
workflow.add_edge("retrieve_node", "approval_node")

workflow.add_conditional_edges(
    "approval_node",
    route_after_approval,
    {
        "crew_node": "crew_node",
        "rewrite_node": "rewrite_node"
    }
)
workflow.add_edge("crew_node", END)

# Compile LangGraph with checkpointer memory saver
memory = MemorySaver()
app_graph = workflow.compile(
    checkpointer=memory,
    interrupt_before=["approval_node"]
)

# API Payload schemas
class StartRequest(BaseModel):
    query: str
    model: str

class ApproveRequest(BaseModel):
    thread_id: str
    approved: bool
    feedback: str = ""

@app.get("/")
def read_root():
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    return {
        "status": "healthy",
        "title": "Multi Agent",
        "openai_configured": bool(openai_key and "your_openai" not in openai_key),
        "gemini_configured": bool(gemini_key and "your_gemini" not in gemini_key),
        "supabase_configured": supabase_client is not None
    }

@app.get("/gui")
def serve_gui():
    from fastapi.responses import HTMLResponse
    # Locate GAS directory inside current folder (Docker build context) or parent project folder
    gas_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "GAS")
    if not os.path.exists(gas_dir):
        gas_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "GAS")
    if not os.path.exists(gas_dir):
        gas_dir = "GAS"
        
    index_path = os.path.join(gas_dir, "index.html")
    style_path = os.path.join(gas_dir, "style.html")
    script_path = os.path.join(gas_dir, "script.html")
    
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        
        style_content = ""
        if os.path.exists(style_path):
            with open(style_path, "r", encoding="utf-8") as f:
                style_content = f.read()
                
        script_content = ""
        if os.path.exists(script_path):
            with open(script_path, "r", encoding="utf-8") as f:
                script_content = f.read()
                
        # Parse standard Apps Script scriptlet syntax
        html = html.replace("<?!= include('style'); ?>", style_content)
        html = html.replace("<?!= include('script'); ?>", script_content)
        return HTMLResponse(content=html, status_code=200)
    else:
        return HTMLResponse(
            content=f"<h3>GUI frontend files not found on server. Inspected path: {os.path.abspath(gas_dir)}</h3>", 
            status_code=404
        )

@app.post("/agent/start")
def start_agent(payload: StartRequest):
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query topic cannot be empty.")
        
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        app_graph.invoke({
            "query": payload.query.strip(),
            "current_query": payload.query.strip(),
            "retrieved_documents": [],
            "approved": False,
            "feedback": "",
            "model": payload.model,
            "loop_step": 0,
            "planner_output": "",
            "writer_output": "",
            "editor_output": "",
            "translation_output": "",
            "messages": [HumanMessage(content=f"주제: {payload.query.strip()}")]
        }, config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start workflow: {str(e)}")
        
    state_info = app_graph.get_state(config)
    next_nodes = state_info.next
    status = "pending_approval" if "approval_node" in next_nodes else "completed"
    
    try:
        mermaid_markup = app_graph.get_graph().draw_mermaid()
    except Exception:
        mermaid_markup = ""
        
    return {
        "thread_id": thread_id,
        "status": status,
        "current_query": state_info.values.get("current_query", ""),
        "retrieved_documents": state_info.values.get("retrieved_documents", []),
        "mermaid": mermaid_markup
    }

@app.post("/agent/approve")
def approve_agent(payload: ApproveRequest):
    config = {"configurable": {"thread_id": payload.thread_id}}
    
    state_info = app_graph.get_state(config)
    if not state_info.values:
        raise HTTPException(status_code=404, detail="Session thread not found.")
        
    app_graph.update_state(
        config,
        {"approved": payload.approved, "feedback": payload.feedback},
        as_node="approval_node"
    )
    
    try:
        app_graph.invoke(None, config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume workflow: {str(e)}")
        
    res_state = app_graph.get_state(config)
    next_nodes = res_state.next
    
    # If it looped back, status will be pending_approval again after running retrieve
    status = "pending_approval" if "approval_node" in next_nodes else "completed"
    
    try:
        mermaid_markup = app_graph.get_graph().draw_mermaid()
    except Exception:
        mermaid_markup = ""
        
    return {
        "thread_id": payload.thread_id,
        "status": status,
        "current_query": res_state.values.get("current_query", ""),
        "retrieved_documents": res_state.values.get("retrieved_documents", []),
        "planner_output": res_state.values.get("planner_output", ""),
        "writer_output": res_state.values.get("writer_output", ""),
        "editor_output": res_state.values.get("editor_output", ""),
        "translation_output": res_state.values.get("translation_output", ""),
        "mermaid": mermaid_markup
    }
