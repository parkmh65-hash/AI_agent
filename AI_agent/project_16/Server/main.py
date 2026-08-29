import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_openai import ChatOpenAI
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langserve import add_routes
from dotenv import load_dotenv

# Load environment variables
dotenv_path = r"C:\Anti-project\.env"
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    load_dotenv()

app = FastAPI(
    title="Langchain Server",
    description="Langserver and FastAPI application for novel and poem generation",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Models
openai_key = os.getenv("OPENAI_API_KEY")
openai_model = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=openai_key or "missing_key"
)

# Ollama 설정 (기본적으로 localhost:11434를 바라보며, 환경변수가 있다면 지정)
ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
llama_model = OllamaLLM(
    model="llm3.1:8b",
    base_url=ollama_host
)

# Prompts
novel_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a professional novelist. Write a beautiful, descriptive, and emotionally rich short novel in Korean. Focus on high literary quality and flow. Return ONLY the novel content without any other explanations or introductory text."),
    ("user", "주제: {topic}")
])

poem_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a professional poet. Write a deeply touching, artistic, and emotional poem in Korean. Return ONLY the poem content without any other explanations or introductory text."),
    ("user", "주제: {topic}")
])

# Chains (StrOutputParser를 통과시켜 깔끔한 문자열 출력을 보장)
chain_openai_novel = novel_prompt | openai_model | StrOutputParser()
chain_openai_poem = poem_prompt | openai_model | StrOutputParser()
chain_llama_novel = novel_prompt | llama_model | StrOutputParser()
chain_llama_poem = poem_prompt | llama_model | StrOutputParser()

# Langserve routes mapping
add_routes(
    app,
    chain_openai_novel,
    path="/openai/novel"
)
add_routes(
    app,
    chain_openai_poem,
    path="/openai/poem"
)
add_routes(
    app,
    chain_llama_novel,
    path="/llama/novel"
)
add_routes(
    app,
    chain_llama_poem,
    path="/llama/poem"
)

@app.get("/")
def read_root():
    return {
        "status": "healthy",
        "title": "Langchain Server",
        "openai_configured": bool(openai_key),
        "ollama_host": ollama_host
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
