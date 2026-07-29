import os
import math
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from dotenv import load_dotenv

# LangChain Imports
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain_core.tools import Tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Supabase
from supabase import create_client

# Load environment variables
dotenv_path = r"C:\Anti-project\.env"
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    load_dotenv()

# Initialize FastAPI
app = FastAPI(
    title="Tool AI Agent",
    description="LangChain agent integrating Wikipedia, arXiv, and Naver News Vector DB",
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

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Supabase REST Client
supabase_client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Failed to initialize Supabase client: {e}")

# Initialize Embeddings
openai_embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=OPENAI_API_KEY
)

# Define Tool Helpers
def query_wikipedia(query: str) -> str:
    from langchain_community.utilities import WikipediaAPIWrapper
    try:
        wrapper = WikipediaAPIWrapper()
        return wrapper.run(query)
    except Exception as e:
        return f"Wikipedia search failed: {str(e)}"

def query_arxiv(query: str) -> str:
    from langchain_community.utilities import ArxivAPIWrapper
    try:
        wrapper = ArxivAPIWrapper()
        return wrapper.run(query)
    except Exception as e:
        return f"ArXiv search failed: {str(e)}"

def query_naver_news_vector_search(query: str) -> str:
    if not supabase_client:
        return "Supabase client is not configured. Cannot perform Naver News Vector Search."

    # 1. Scrape Naver News using robust DOM-walking selector logic
    url = "https://search.naver.com/search.naver"
    params = {"where": "news", "query": query}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        res = requests.get(url, params=params, headers=headers, timeout=5)
        res.raise_for_status()
    except Exception as e:
        return f"Failed to fetch Naver news: {str(e)}"

    soup = BeautifulSoup(res.text, "html.parser")
    news_items = []
    
    for title_a in soup.find_all("a"):
        if title_a.get("data-heatmap-target") == ".tit":
            title = title_a.get_text(strip=True).replace("새 창 열림", "").strip()
            link = title_a.get("href")
            
            # Walk up parents to locate description block
            desc = ""
            parent = title_a.parent
            levels = 0
            while parent and parent.name != "body" and levels < 5:
                desc_a = parent.find("a", {"data-heatmap-target": ".body"})
                if desc_a:
                    desc = desc_a.get_text(strip=True).replace("새 창 열림", "").strip()
                    break
                parent = parent.parent
                levels += 1
                
            news_items.append({
                "title": title,
                "link": link,
                "description": desc
            })
            if len(news_items) >= 5:
                break

    if not news_items:
        return f"No Naver news found for query: {query}"

    # 2. Vectorize and save to Supabase
    for item in news_items:
        content = f"제목: {item['title']}\n링크: {item['link']}\n내용: {item['description']}"
        metadata = {
            "source": "naver_news",
            "title": item["title"],
            "link": item["link"]
        }
        
        try:
            # Embed content
            embedding_vector = openai_embeddings.embed_query(content)
            
            # Insert into database documents table
            supabase_client.table("documents").insert({
                "content": content,
                "metadata": metadata,
                "embedding": embedding_vector
            }).execute()
        except Exception as e:
            print(f"Error saving to Supabase: {str(e)}")

    # 3. Retrieve relevant documents from Supabase Vector DB
    try:
        query_vector = openai_embeddings.embed_query(query)
    except Exception as e:
        return f"Failed to generate embedding for query: {str(e)}"

    # Try RPC similarity search fallback
    try:
        rpc_res = supabase_client.rpc("match_documents", {
            "query_embedding": query_vector,
            "match_threshold": 0.0,
            "match_count": 3
        }).execute()
        results = rpc_res.data or []
    except Exception as e:
        print(f"match_documents RPC failed: {str(e)}. Falling back to Python-side similarity search.")
        # Fallback: Fetch all documents and calculate similarity in memory
        try:
            db_res = supabase_client.table("documents").select("id, content, metadata, embedding").execute()
            if db_res.data:
                def cosine_similarity(v1, v2):
                    dot = sum(x*y for x, y in zip(v1, v2))
                    mag1 = math.sqrt(sum(x*x for x in v1))
                    mag2 = math.sqrt(sum(y*y for y in v2))
                    return dot / (mag1 * mag2) if mag1 > 0 and mag2 > 0 else 0

                scored_docs = []
                for row in db_res.data:
                    emb = row.get("embedding")
                    if isinstance(emb, str):
                        emb = [float(x) for x in emb.strip("[]").split(",")]
                    elif isinstance(emb, list):
                        emb = [float(x) for x in emb]
                    else:
                        continue
                    
                    score = cosine_similarity(query_vector, emb)
                    scored_docs.append({
                        "content": row["content"],
                        "metadata": row["metadata"],
                        "similarity": score
                    })
                scored_docs.sort(key=lambda x: x["similarity"], reverse=True)
                results = scored_docs[:3]
            else:
                results = []
        except Exception as ex:
            return f"Failed to retrieve documents via fallback: {str(ex)}"

    # Format output results
    formatted_results = []
    for idx, doc in enumerate(results):
        formatted_results.append(
            f"[{idx+1}] {doc['content']}\n(유사도: {doc.get('similarity', doc.get('score', 0.0)):.4f})"
        )
    return "\n\n".join(formatted_results)

# Create LangChain Tools
wikipedia_tool = Tool(
    name="Wikipedia",
    func=query_wikipedia,
    description="Use this tool to search Wikipedia for factual information about history, geography, people, and general knowledge."
)

arxiv_tool = Tool(
    name="arXiv",
    func=query_arxiv,
    description="Use this tool to search scientific papers and academic articles from arXiv. Useful for technical queries, deep learning, physics, and computer science topics."
)

naver_news_tool = Tool(
    name="Naver_News_Vector_Search",
    func=query_naver_news_vector_search,
    description="Use this tool to search recent Naver news articles. It fetches the latest news, vectorizes and stores them in Supabase, and retrieves the most relevant articles."
)

# API schemas
class AgentRunRequest(BaseModel):
    query: str
    model: str  # "openai" or "gemini"
    tools: List[str]  # e.g., ["wikipedia", "arxiv", "naver_news"]

class AgentRunResponse(BaseModel):
    results: Dict[str, str]

@app.get("/")
def read_root():
    return {
        "status": "healthy",
        "title": "Tool AI Agent Server",
        "openai_configured": bool(OPENAI_API_KEY),
        "gemini_configured": bool(GEMINI_API_KEY),
        "supabase_configured": bool(SUPABASE_URL and SUPABASE_KEY)
    }

@app.post("/agent/run", response_model=AgentRunResponse)
def run_agent(payload: AgentRunRequest):
    # 1. Initialize selected LLM
    if payload.model == "gemini":
        if not GEMINI_API_KEY:
            raise HTTPException(status_code=400, detail="Gemini API Key is not configured on the server.")
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=GEMINI_API_KEY,
            temperature=0.3
        )
    else:
        if not OPENAI_API_KEY:
            raise HTTPException(status_code=400, detail="OpenAI API Key is not configured on the server.")
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=OPENAI_API_KEY,
            temperature=0.3
        )

    # 2. Execute tool runs
    results = {}
    
    for tool_name in payload.tools:
        # Resolve tool
        if tool_name == "wikipedia":
            active_tool = wikipedia_tool
            fallback_func = query_wikipedia
        elif tool_name == "arxiv":
            active_tool = arxiv_tool
            fallback_func = query_arxiv
        elif tool_name == "naver_news":
            active_tool = naver_news_tool
            fallback_func = query_naver_news_vector_search
        else:
            continue

        # Try running ReAct agent using custom create_agent
        try:
            agent = create_agent(llm, [active_tool])
            res = agent.invoke({"messages": [("user", f"Use the tool to answer this question: {payload.query}. Answer in Korean.")]})
            results[tool_name] = res["messages"][-1].content
            
        except Exception as e:
            # Fallback to direct tool call and prompt synthesis
            print(f"Agent execution failed for {tool_name} ({e}). Running fallback synthesis chain.")
            try:
                # Call tool directly
                tool_output = fallback_func(payload.query)
                
                # Direct synthesize
                synthesis_prompt = ChatPromptTemplate.from_messages([
                    ("system", "You are a helpful assistant. Based on the provided raw tool output, synthesize a complete and well-structured answer in Korean to the user's question. Be informative and organized."),
                    ("user", "User Question: {query}\n\nRaw Tool Output:\n{tool_output}\n\nAnswer:")
                ])
                chain = synthesis_prompt | llm | StrOutputParser()
                results[tool_name] = chain.invoke({"query": payload.query, "tool_output": tool_output})
            except Exception as fe:
                results[tool_name] = f"Error performing search and synthesis: {str(fe)}"

    return AgentRunResponse(results=results)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
