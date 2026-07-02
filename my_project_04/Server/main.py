import os
import time
from datetime import datetime
from typing import Annotated, TypedDict, List
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# LangChain / LangGraph imports
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Models & Vector Store
from supabase import create_client
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.vectorstores import SupabaseVectorStore

# Load environment variables (handling case where .env is in parent directories)
current_file_dir = os.path.dirname(os.path.abspath(__file__))
parent_dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(current_file_dir))), ".env")
if os.path.exists(parent_dotenv_path):
    load_dotenv(dotenv_path=parent_dotenv_path)
else:
    load_dotenv()

# --- STATE DEFINITION ---
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    context: str
    db_row_count: int

# --- NODE 1: RETRIEVE NODE ---
def retrieve_node(state: AgentState):
    """
    Retrieves context from Supabase Vector Store.
    Gracefully falls back if credentials are missing or database fails.
    """
    # Get last user query
    last_msg_content = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage) or (hasattr(msg, 'type') and msg.type == 'human'):
            last_msg_content = msg.content
            break
            
    if not last_msg_content:
        return {"context": "[안내: 사용자 입력 메시지를 찾지 못했습니다.]", "db_row_count": 0}

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key or supabase_url == "your_supabase_url_here":
        return {"context": "[안내: Supabase DB 설정이 누락되었습니다. RAG 검색 없이 답변을 생성합니다.]", "db_row_count": 0}

    try:
        # Initialize Supabase client
        supabase_client = create_client(supabase_url, supabase_key)
        
        # Get total row count from database for diagnostics
        db_count = 0
        try:
            res = supabase_client.table("documents").select("id", count="exact").limit(1).execute()
            db_count = res.count if res.count is not None else 0
        except Exception as e_count:
            print(f"[Warn] Failed to get row count: {e_count}")

        # Initialize embeddings (OpenAI)
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key and openai_key != "your_openai_api_key_here":
            embeddings = OpenAIEmbeddings(model="text-embedding-3-small", dimensions=768)
        else:
            # Fallback to Google embeddings if OpenAI key is missing
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
            
        # Embed user query
        query_vector = embeddings.embed_query(last_msg_content)
        
        # Execute direct RPC similarity search compatible with the custom db schema
        rpc_res = supabase_client.rpc(
            "match_documents",
            {
                "query_embedding": query_vector,
                "match_count": 3,
                "match_threshold": -1.0 # -1.0 returns all documents (we retrieve the top 3 closest vectors)
            }
        ).execute()
        
        retrieved_docs = rpc_res.data or []
        context_text = "\n\n".join([doc.get("content", "") for doc in retrieved_docs if doc.get("content")])
        
        if not context_text.strip():
            context_text = "[안내: 검색 결과에 일치하는 문서가 없습니다. 일반 지식으로 답변을 구성합니다.]"
            
        return {"context": context_text, "db_row_count": db_count}
        
    except Exception as e:
        print(f"[Error in Retrieve Node] {e}")
        return {"context": f"[안내: 벡터 DB 검색 실패. 일반 지식으로 답변합니다. 에러: {str(e)}]", "db_row_count": 0}

# --- NODE 2: ASSISTANT NODE (LLM LangChain 구성) ---
def assistant_node(state: AgentState):
    """
    Generates response using custom prompt template, LLM (OpenAI GPT), and output parser.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    
    # 1. LLM 초기화 (prompt, llm, output_parser로 랭체인 구성)
    if openai_key and openai_key != "your_openai_api_key_here":
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
    else:
        # Fallback to Gemini if OpenAI API Key is not set
        print("[Info] OpenAI API Key missing. Falling back to Gemini 1.5 Flash.")
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.7)

    # 2. Prompt 구성
    context = state.get("context", "")
    prompt = ChatPromptTemplate.from_messages([
        ("system", "너는 친절하고 유능한 AI 비서 '인공지능 시안'이다. 다음 문맥(Context)을 최대한 참고하여 사용자의 질문에 한국어로 성실하게 답변하라. 문맥에 정보가 부족하더라도 아는 한도 내에서 자연스럽게 대답해 주어야 한다.\n\n[Context]\n{context}"),
        ("placeholder", "{messages}")
    ])
    
    # 3. Output Parser 구성
    output_parser = StrOutputParser()
    
    # 4. Chain 구성 (prompt | llm | output_parser)
    chain = prompt | llm | output_parser
    
    # Run Chain
    response_text = chain.invoke({
        "context": context,
        "messages": state["messages"]
    })
    
    # Return message update
    return {"messages": [AIMessage(content=response_text)]}

# --- LANGGRAPH FLOW CONFIGURATION ---
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("assistant", assistant_node)

# Setup edges
workflow.add_edge(START, "retrieve")
workflow.add_edge("retrieve", "assistant")
workflow.add_edge("assistant", END)

# Compile graph
graph = workflow.compile()


# --- FASTAPI SERVER SETUP ---
app = FastAPI(
    title="project_04 AI Server (pr_04)",
    description="FastAPI + LangChain + LangGraph + RAG (Supabase Vector DB) backend.",
    version="1.0.0"
)

# Enable CORS for external browser and Google Apps Script integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Input/Output Schemas
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str
    db_row_count: int
    execution_time_sec: float
    response_time: str

@app.get("/")
def read_root():
    """
    Health check endpoint that returns database size statistics.
    """
    db_count = 0
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if supabase_url and supabase_key and supabase_url != "your_supabase_url_here":
        try:
            supabase_client = create_client(supabase_url, supabase_key)
            res = supabase_client.table("documents").select("id", count="exact").limit(1).execute()
            db_count = res.count if res.count is not None else 0
        except Exception as e:
            print(f"[Error GET /] {e}")

    return {
        "status": "online",
        "service": "pr_04 AI Server",
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "db_row_count": db_count
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Receives message, executes the LangGraph agent pipeline, and returns the result.
    """
    start_time = time.time()
    
    # Initialize state with user's input
    initial_state = AgentState(
        messages=[HumanMessage(content=request.message)],
        context="",
        db_row_count=0
    )
    
    try:
        # Execute LangGraph workflow synchronously (in executor to avoid blocking event loop)
        import asyncio
        loop = asyncio.get_event_loop()
        final_state = await loop.run_in_executor(None, graph.invoke, initial_state)
        
        # Extract reply from final state
        reply_message = final_state["messages"][-1]
        reply_text = reply_message.content if hasattr(reply_message, 'content') else str(reply_message)
        
        execution_time = time.time() - start_time
        response_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        return ChatResponse(
            reply=reply_text,
            db_row_count=final_state.get("db_row_count", 0),
            execution_time_sec=execution_time,
            response_time=response_time_str
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Pipeline Execution Error: {str(e)}")
