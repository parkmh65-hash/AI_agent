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
from langchain_core.tools import tool
from langchain_core.documents import Document
from langchain_core.messages import ToolMessage, AIMessage, HumanMessage, SystemMessage
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
    title="Agentic RAG",
    description="Agentic RAG using LangChain, LangGraph, and Supabase Vector DB with Query Rewriting and Human-in-the-Loop review.",
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
    
    # Check if Gemini key is actual key or placeholder
    is_gemini_valid = gemini_key and "your_gemini_api" not in gemini_key
    is_openai_valid = openai_key and "your_openai_api" not in openai_key
    
    if model_name == "gemini":
        if is_gemini_valid:
            return ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=gemini_key,
                temperature=temperature
            )
        elif is_openai_valid:
            # Fallback to OpenAI if selected model is Gemini but no key exists
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

# Helper to get the correct embeddings model
def get_embeddings():
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    is_openai_valid = openai_key and "your_openai_api" not in openai_key
    is_gemini_valid = gemini_key and "your_gemini_api" not in gemini_key
    
    if is_openai_valid:
        # Default text-embedding-3-small outputs 1536 dimensions, which matches database vector(1536)
        return OpenAIEmbeddings(model="text-embedding-3-small", api_key=openai_key)
    elif is_gemini_valid:
        # Google's text-embedding-004 outputs 768 dimensions. We wrap it to pad to 1536 dimensions.
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
        # Dummy embedding for testing if offline/no credentials
        class DummyEmbeddings:
            def embed_documents(self, texts):
                return [[0.0] * 1536 for _ in texts]
            def embed_query(self, text):
                return [0.0] * 1536
        return DummyEmbeddings()


# Mock Financial Data for robust RAG fallbacks
MOCK_FINANCIAL_ARTICLES = [
    {
        "title": "삼성전자 2분기 영업이익 10조 원 돌파 및 HBM3E 반도체 실적 분석",
        "url": "https://finance.naver.com/news/samsung_electronics_q2",
        "content": "삼성전자가 2026년 2분기 영업이익 10조 원을 돌파하며 반도체 부문의 강력한 회복세를 증명했습니다. 메모리 반도체 HBM3E 공급 본격화와 디스플레이 사업부의 유기발광다이오드(OLED) 매출 증가가 실적 성장을 견인했습니다. 모바일 사업부는 갤럭시 S26 시리즈의 판매 호조로 안정적인 실적을 유지했습니다. 그러나 파운드리 미세공정 수율 개선이 예상보다 지연되는 점과 시스템LSI 사업부의 적자 지속은 단기적인 하방 리스크로 꼽힙니다. 증권가에서는 하반기 반도체 공급 부족에 따른 단가 상승으로 추가 이익 확대가 기대된다고 평가했습니다."
    },
    {
        "title": "한국은행 기준금리 인하 및 한국 미국 긴축 완화 흐름 전망",
        "url": "https://finance.yahoo.com/news/bok_interest_rates",
        "content": "미국 연방준비제도(Fed)가 최근 물가 상승 압력 완화와 실업률 상승 압력에 대응해 선제적 금리 인하(빅컷, 0.5%p 인하)를 단행했습니다. 이에 따라 한국은행 금융통화위원회도 연 3.50%인 기준금리를 3.25%로 인하하며 긴축 통화 정책 기조에서 점진적 완화로 선회했습니다. 금리 인하로 인해 국내 가계부채 증가와 수도권 부동산 시장 불안정성이 다시 우려되고 있으나, 중소기업의 이자 부담 완화와 소비 진작 효과가 더 클 것으로 기대됩니다. 금리 인하 사이클이 시작되면서 채권 시장으로의 자금 유입이 증가하고 있으며 원/달러 환율은 1320원 선에서 하향 안정 흐름을 보이고 있습니다."
    },
    {
        "title": "글로벌 AI 반도체 엔비디아 Blackwell 공급 및 빅테크 칩 경쟁 동향",
        "url": "https://finance.daum.net/news/ai_semiconductors_nvidia",
        "content": "엔비디아가 독점해 온 AI 반도체 시장에 AMD, 인텔 및 빅테크 기업들(구글, 메타, 아마존)이 맞춤형 칩(ASIC)을 앞세워 강력한 도전장을 던지고 있습니다. 최근 구글은 차세대 TPU v6를 발표하며 자체 AI 인프라 효율성을 극대화했고, 메타는 자체 추론 칩인 MTIA의 차세대 버전을 상용화했습니다. 이에 맞서 엔비디아는 Blackwell 아키텍처 기반의 차세대 칩 공급을 본격화하며 시장 점유율 85% 이상을 수성하기 위해 총력을 다하고 있습니다. AI 학습 비용 절감과 전력 소비 효율화가 빅테크의 핵심 과제로 떠오르면서 고성능 저전력 칩의 수요는 지속 증가할 전망입니다."
    },
    {
        "title": "글로벌 증시 및 금 국제 유가 원자재 자산 시장 동향",
        "url": "https://finance.naver.com/news/global_market_commodities",
        "content": "글로벌 공급망 불확실성과 지정학적 긴장이 고조되면서 안전자산인 금 가격이 역대 최고치를 경신했습니다. 온스당 2,500달러 선을 상회하며 글로벌 인플레이션 헷지 수요가 급증하고 있습니다. 국제 유가(WTI)는 중동 지역 지정학적 리스크와 OPEC+의 감산 합의 영향으로 배럴당 75~85달러 범위에서 강보합세를 보이고 있습니다. 반면, 중국의 경기 둔화 우려로 구리 등 산업용 원자재 가격은 제한적인 움직임을 나타내고 있으며 코스피 지수는 외국인의 IT 업종 순매수세에 힘입어 2,600선을 수성하고 있습니다."
    }
]

# Database Seed Endpoint (Scrapes financial pages or inserts fallback documents)
@app.post("/db/seed")
def seed_database():
    if not supabase_client:
        raise HTTPException(
            status_code=400,
            detail="Supabase is not configured. Please set SUPABASE_URL and SUPABASE_KEY in .env."
        )
    
    from langchain_community.document_loaders import WebBaseLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import SupabaseVectorStore
    
    # Financial URLs
    urls = [
        "https://finance.naver.com",
        "https://finance.yahoo.com",
        "https://finance.daum.net"
    ]
    
    docs = []
    
    print("Starting Web Crawling...")
    for url in urls:
        try:
            # Attempt to scrape with WebBaseLoader
            loader = WebBaseLoader(url)
            # Customizing headers to prevent 403 Forbidden on some websites
            loader.requests_kwargs = {"headers": {"User-Agent": "Mozilla/5.0"}}
            scraped_docs = loader.load()
            
            # Clean scraped content a bit
            for sd in scraped_docs:
                if len(sd.page_content.strip()) > 100:
                    sd.metadata["source"] = url
                    docs.append(sd)
                    print(f"Successfully scraped: {url} (Length: {len(sd.page_content)})")
        except Exception as e:
            print(f"Failed to scrape {url}: {e}. Skipping and fallback will be included.")
            
    # Always merge fallback high-quality financial data so search runs well
    print("Adding fallback financial data articles...")
    for article in MOCK_FINANCIAL_ARTICLES:
        docs.append(
            Document(
                page_content=article["content"],
                metadata={"title": article["title"], "source": article["url"]}
            )
        )
        
    # Text Splitting
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    chunks = text_splitter.split_documents(docs)
    print(f"Generated {len(chunks)} chunks for database.")
    
    # Save to Supabase vector store
    try:
        embeddings = get_embeddings()
        
        # In order to prevent stacking endless duplicate copies on every seed call, 
        # let's try to clear previous documents if needed, or simply write new ones.
        SupabaseVectorStore.from_documents(
            documents=chunks,
            embedding=embeddings,
            client=supabase_client,
            table_name="documents",
            query_name="match_documents"
        )
        return {
            "status": "success",
            "message": f"Successfully ingested {len(chunks)} text chunks into Supabase Vector Store."
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to embed and save to Supabase: {str(e)}. Ensure the pgvector table 'documents' and function 'match_documents' exist."
        )

# Retrieval Tool Definition
def perform_retrieval(query: str) -> List[Document]:
    if not supabase_client:
        # Fallback to local mock search if supabase is not set
        print("[WARNING] Supabase not initialized. Searching mock data local.")
        query_words = query.split()
        hits = []
        for article in MOCK_FINANCIAL_ARTICLES:
            score = sum(1 for w in query_words if w in article["content"] or w in article["title"])
            if score > 0:
                hits.append(Document(page_content=article["content"], metadata={"source": article["url"]}))
        return hits[:3] if hits else [Document(page_content="검색 결과를 찾을 수 없으며 Supabase 연동이 구성되지 않았습니다.", metadata={"source": "mock"})]
        
    try:
        embeddings = get_embeddings()
        query_vec = embeddings.embed_query(query)
        
        # Call match_documents RPC directly with expected parameters only
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
            content = row.get("content", "")
            metadata = row.get("metadata", {}) or {}
            if not isinstance(metadata, dict):
                metadata = {}
            metadata["source"] = row.get("source", metadata.get("source", "unknown"))
            docs.append(Document(page_content=content, metadata=metadata))
        return docs
    except Exception as e:
        print(f"Error searching vector store via RPC: {e}")
        # Fallback to mock logic if error occurs
        return [Document(page_content=f"Supabase 검색 중 오류가 발생했습니다: {str(e)}", metadata={"source": "error"})]


# Define LangGraph state dictionary
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    query: str
    current_query: str
    selected_sections: List[str]
    retrieved_documents: List[Any]
    recipe_draft: Dict[str, str]  # Holds drafts for each chosen report section
    recipe_final: Dict[str, str]  # Holds final answers
    feedback: str
    approved: bool
    model: str
    loop_step: int

# --- NODE: Agent Decision Node ---
def agent_node(state: AgentState):
    query = state["current_query"]
    messages = list(state.get("messages", []))
    
    # Prompt explaining to the Agent what it is doing
    prompt = (
        f"당신은 금융 정보 탐색 에이전트입니다. 사용자의 질문: '{query}'\n"
        f"정보를 벡터 데이터베이스에서 검색하려면 'retrieve' 도구를 실행하고, "
        f"이미 필요한 금융 정보가 충분히 수집되었거나 검색을 마쳤다면 결과를 정리하여 답변 생성으로 넘어가세요.\n"
        f"수집된 문서 개수: {len(state.get('retrieved_documents', []) or [])}개."
    )
    
    # We append a instruction message
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages.insert(0, SystemMessage(content="You are a financial information retrieval agent. Your goal is to retrieve accurate financial details."))
        
    # We invoke the LLM
    llm = get_llm(state["model"])
    
    # If retrieve tool is not yet called, suggest tool invocation
    if not state.get("retrieved_documents"):
        # Force/encourage tool call
        res = AIMessage(
            content="질문에 답하기 위한 최신 금융 데이터를 검색하겠습니다.",
            tool_calls=[{
                "name": "retrieve",
                "args": {"query": query},
                "id": "call_" + str(uuid.uuid4())[:8]
            }]
        )
    else:
        res = AIMessage(content="금융 데이터 검색 결과를 분석하여 답변을 생성하도록 하겠습니다.")
        
    messages.append(res)
    return {"messages": messages}

# --- NODE: Retrieve Node ---
def retrieve_node(state: AgentState):
    query = state["current_query"]
    messages = list(state.get("messages", []))
    
    # Locate tool call
    last_message = messages[-1]
    tool_call_id = last_message.tool_calls[0]["id"] if last_message.tool_calls else "manual"
    
    print(f"Retrieving documents for: {query}")
    docs = perform_retrieval(query)
    
    # Format document contents as tool response message
    context_str = "\n\n".join([f"Source: {d.metadata.get('source', 'unknown')}\nContent: {d.page_content}" for d in docs])
    tool_msg = ToolMessage(content=context_str, tool_call_id=tool_call_id)
    messages.append(tool_msg)
    
    return {
        "messages": messages,
        "retrieved_documents": docs
    }

# --- CONDITIONAL ROUTER: Grader ---
# Structure output format for grading
class Grade(BaseModel):
    binary_score: str = Field(
        description="Relevance check result of retrieved documents to the query. Yes or No.",
        pattern="^(yes|no)$"
    )

def grade_documents_edge(state: AgentState):
    # Retrieve model and queries
    model_name = state["model"]
    query = state["current_query"]
    docs = state.get("retrieved_documents", [])
    loop_step = state.get("loop_step", 0)
    
    if not docs:
        print("No documents found, routing to rewrite.")
        return "rewrite"
        
    # Force proceed to generate if we have looped too many times to prevent infinite cycle
    if loop_step >= 2:
        print("Max rewrite loop reached. Proceeding to generate.")
        return "generate"
        
    llm = get_llm(model_name)
    
    # Prompt for grading
    prompt = (
        f"당신은 검색된 문서가 사용자의 금융 질문에 부합하는지 평가하는 평가자입니다.\n"
        f"사용자 질문: {query}\n\n"
        f"검색된 문서들:\n"
        f"{chr(10).join([d.page_content for d in docs])}\n\n"
        f"문서들이 사용자의 질문에 직접 대답하기 위한 유용한 금융 분석 정보를 포함하고 있습니까?\n"
        f"답은 반드시 'yes' 또는 'no' 중 하나여야 합니다."
    )
    
    try:
        # Use structured outputs
        structured_llm = llm.with_structured_output(Grade)
        res = structured_llm.invoke(prompt)
        score = res.binary_score.lower().strip()
        print(f"Document Relevance Grade Result: {score}")
    except Exception as e:
        print(f"Grading error: {e}. Defaulting to yes to proceed.")
        score = "yes"
        
    if score == "yes":
        return "generate"
    else:
        return "rewrite"

# --- NODE: Rewrite Node ---
def rewrite_node(state: AgentState):
    model_name = state["model"]
    query = state["current_query"]
    loop_step = state.get("loop_step", 0)
    
    llm = get_llm(model_name)
    
    prompt = (
        f"당신은 금융 정보 RAG 시스템을 위한 질문 재작성자입니다.\n"
        f"사용자의 이전 질문은 '{query}' 이었으나, 관련 금융 문서가 검색되지 않았거나 불충분했습니다.\n"
        f"동일한 핵심 의미를 유지하면서, 네이버/야후/다음 금융 기사에서 보다 쉽게 검색될 수 있도록 "
        f"명확하고 검색어 위주인 단일 질문으로 재작성해 주세요.\n"
        f"인사말이나 군더더기 없이 재작성된 질문만 한 줄로 출력하세요."
    )
    
    try:
        res = llm.invoke(prompt)
        rewritten_query = res.content.strip().replace('"', '').replace("'", "")
        print(f"Query rewritten: '{query}' -> '{rewritten_query}'")
    except Exception as e:
        print(f"Rewriting error: {e}")
        rewritten_query = query
        
    messages = list(state.get("messages", []))
    messages.append(AIMessage(content=f"질문을 재작성했습니다: '{rewritten_query}'"))
    
    return {
        "messages": messages,
        "current_query": rewritten_query,
        "loop_step": loop_step + 1
    }

# --- NODE: Generate Node (Generates draft sections) ---
def generate_node(state: AgentState):
    model_name = state["model"]
    query = state["query"]
    docs = state.get("retrieved_documents", [])
    sections = state.get("selected_sections", ["analysis"])
    
    llm = get_llm(model_name)
    
    context_text = "\n\n".join([f"[문서] {d.page_content}" for d in docs])
    
    section_names = {
        "analysis": "시장 분석 및 동향 (Market Analysis)",
        "risks": "리스크 및 주요 요인 (Risks & Factors)",
        "opinion": "종합 투자의견 (Investment Opinion)"
    }
    
    drafts = state.get("recipe_draft", {}) or {}
    
    # Generate content for each requested section
    for sec in sections:
        sec_label = section_names.get(sec, sec)
        prompt = (
            f"당신은 전문 금융 분석가입니다. 아래 제공된 검색 문서 맥락(Context)을 활용하여 "
            f"주제 '{query}'에 대한 리포트 중 [{sec_label}] 항목을 작성해 주세요.\n\n"
            f"검색된 금융 문서 맥락:\n{context_text}\n\n"
            f"작성 규칙:\n"
            f"1. 인사말이나 리포트 서두, 맺음말 없이 오직 해당 [{sec_label}] 본문 글만 작성하세요.\n"
            f"2. 마크다운 형식으로 핵심 정보가 드러나도록 문단을 나누고 깔끔하게 정리하세요.\n"
            f"3. 만약 검색 맥락에 관련 내용이 없다면 일반적인 분석 지식을 활용하되, 맥락을 참고했음을 표시하세요."
        )
        
        try:
            res = llm.invoke(prompt)
            drafts[sec] = res.content.strip()
        except Exception as e:
            print(f"Error generating section {sec}: {e}")
            drafts[sec] = f"[{sec_label}] 생성 중 오류 발생: {str(e)}"
            
    messages = list(state.get("messages", []))
    messages.append(AIMessage(content="금융 분석 보고서 초안이 작성되었습니다. 검토를 위해 대기합니다."))
    
    return {
        "messages": messages,
        "recipe_draft": drafts
    }

# --- NODE: Draft state forward node ---
def draft_node(state: AgentState):
    return state

# --- NODE: Approval Node (Interrupt Breakpoint Placeholder) ---
def approval_node(state: AgentState):
    return state

# --- NODE: Revise Node (Updates draft using user feedback) ---
def revise_node(state: AgentState):
    model_name = state["model"]
    query = state["query"]
    drafts = state.get("recipe_draft", {}) or {}
    feedback = state.get("feedback", "")
    
    llm = get_llm(model_name)
    
    revised_drafts = {}
    section_names = {
        "analysis": "시장 분석 및 동향 (Market Analysis)",
        "risks": "리스크 및 주요 요인 (Risks & Factors)",
        "opinion": "종합 투자의견 (Investment Opinion)"
    }
    
    # Revise each draft section with user feedback
    for sec, content in drafts.items():
        sec_label = section_names.get(sec, sec)
        prompt = (
            f"당신은 금융 분석가입니다. 주제 '{query}' 리포트의 [{sec_label}] 초안 내용입니다:\n"
            f"====================\n"
            f"{content}\n"
            f"====================\n\n"
            f"사용자 피드백: {feedback}\n\n"
            f"사용자의 수정 피드백을 충실하게 반영하여 [{sec_label}] 초안 내용을 전면 개정해 주세요.\n"
            f"다른 인사말은 절대 포함하지 말고 리포트 본문 텍스트만 출력하세요."
        )
        
        try:
            res = llm.invoke(prompt)
            revised_drafts[sec] = res.content.strip()
        except Exception as e:
            print(f"Revision error on {sec}: {e}")
            revised_drafts[sec] = content + f"\n(수정 실패 - 피드백 미반영: {feedback})"
            
    messages = list(state.get("messages", []))
    messages.append(HumanMessage(content=f"피드백 반영 요청: {feedback}"))
    messages.append(AIMessage(content="피드백을 반영하여 금융 보고서 내용을 수정했습니다."))
    
    return {
        "recipe_draft": revised_drafts,
        "feedback": "",  # Clear feedback once applied
        "messages": messages
    }

# --- NODE: Finalize Node (Formats reports in markdown) ---
def finalize_node(state: AgentState):
    model_name = state["model"]
    query = state["query"]
    drafts = state.get("recipe_draft", {}) or {}
    
    llm = get_llm(model_name)
    
    final_output = {}
    section_names = {
        "analysis": "시장 분석 및 동향 (Market Analysis)",
        "risks": "리스크 및 주요 요인 (Risks & Factors)",
        "opinion": "종합 투자의견 (Investment Opinion)"
    }
    
    # Generate final high-quality markdown for each section
    for sec, content in drafts.items():
        sec_label = section_names.get(sec, sec)
        prompt = (
            f"당신은 전문 금융 에디터입니다. 주제 '{query}'의 [{sec_label}] 초안을 가공하여 "
            f"최종 보고서용 고품질 마크다운 형식으로 편집해 주세요. 가독성이 뛰어난 제목 구조, 중요 문구 강조, "
            f"그리고 깔끔한 정리 방식을 반영해 주세요.\n\n"
            f"초안 내용:\n{content}"
        )
        
        try:
            res = llm.invoke(prompt)
            final_output[sec] = res.content.strip()
        except Exception as e:
            print(f"Finalization error on {sec}: {e}")
            final_output[sec] = content
            
    messages = list(state.get("messages", []))
    messages.append(AIMessage(content="금융 보고서 작성이 최종 완료되었습니다!"))
    
    return {
        "recipe_final": final_output,
        "messages": messages
    }

# --- CONDITIONAL ROUTER: Route after approval breakpoint ---
def route_after_approval(state: AgentState):
    if state.get("approved"):
        return "finalize_node"
    else:
        return "revise_node"

# --- CONDITIONAL ROUTER: Routing agent node ---
def route_agent_edge(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]
    
    # Check if agent called a tool
    if last_message.tool_calls:
        return "retrieve"
    else:
        return "generate"

# Build the LangGraph StateGraph workflow
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("agent", agent_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("rewrite", rewrite_node)
workflow.add_node("generate", generate_node)
workflow.add_node("draft_node", draft_node)
workflow.add_node("approval_node", approval_node)
workflow.add_node("revise_node", revise_node)
workflow.add_node("finalize_node", finalize_node)

# Set Entry point
workflow.set_entry_point("agent")

# Add edges and conditional routing
workflow.add_conditional_edges(
    "agent",
    route_agent_edge,
    {
        "retrieve": "retrieve",
        "generate": "generate"
    }
)

# After retrieve, evaluate document relevance
workflow.add_conditional_edges(
    "retrieve",
    grade_documents_edge,
    {
        "generate": "generate",
        "rewrite": "rewrite"
    }
)

# After rewrite, loop back to agent to retry search
workflow.add_edge("rewrite", "agent")

# After generate, transition to draft compilation and pause at approval node
workflow.add_edge("generate", "draft_node")
workflow.add_edge("draft_node", "approval_node")

# Conditional edges from approval node (decided after breakpoint is resumed)
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

# Compile Graph with checkpointer memory saver and approval breakpoint
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
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    return {
        "status": "healthy",
        "title": "Agentic RAG",
        "openai_configured": bool(openai_key and "your_openai" not in openai_key),
        "gemini_configured": bool(gemini_key and "your_gemini" not in gemini_key),
        "supabase_configured": supabase_client is not None
    }

@app.post("/agent/start")
def start_agent(payload: StartRequest):
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    if not payload.sections:
        raise HTTPException(status_code=400, detail="At least one section must be selected.")
        
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    # Start graph execution
    try:
        app_graph.invoke({
            "query": payload.query.strip(),
            "current_query": payload.query.strip(),
            "selected_sections": payload.sections,
            "retrieved_documents": [],
            "recipe_draft": {},
            "recipe_final": {},
            "feedback": "",
            "approved": False,
            "model": payload.model,
            "loop_step": 0,
            "messages": [HumanMessage(content=f"금융 질문: {payload.query.strip()}")]
        }, config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph execution failed: {str(e)}")
        
    # Get current graph state values
    state_info = app_graph.get_state(config)
    next_nodes = state_info.next
    
    status = "pending_approval" if "approval_node" in next_nodes else "completed"
    
    # Generate Mermaid markup for UI diagram
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
            if m.content and not isinstance(m, SystemMessage)
        ],
        "mermaid": mermaid_markup
    }

@app.post("/agent/approve")
def approve_agent(payload: ApproveRequest):
    config = {"configurable": {"thread_id": payload.thread_id}}
    
    state_info = app_graph.get_state(config)
    if not state_info.values:
        raise HTTPException(status_code=404, detail="Thread not found or session expired.")
        
    # Update state value with user approval decision
    app_graph.update_state(
        config,
        {"approved": payload.approved, "feedback": payload.feedback},
        as_node="approval_node"
    )
    
    # Resume graph execution
    try:
        app_graph.invoke(None, config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resuming graph execution failed: {str(e)}")
        
    # Retrieve updated values
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
            if m.content and not isinstance(m, SystemMessage)
        ],
        "mermaid": mermaid_markup
    }

if __name__ == "__main__":
    import uvicorn
    # Use PORT from environment or default to 8080
    port = int(os.getenv("PORT", 8080))
    print(f"Starting server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
