import os
import time
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

# Load environment variables
current_file_dir = os.path.dirname(os.path.abspath(__file__))
parent_dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(current_file_dir))), ".env")
if os.path.exists(parent_dotenv_path):
    load_dotenv(dotenv_path=parent_dotenv_path)
else:
    load_dotenv()

app = FastAPI(
    title="project_05 OpenAI Responses API Server",
    description="FastAPI server integrated with OpenAI Responses API for literary QA.",
    version="2.0.0"
)

# Enable CORS for Google Apps Script access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Retrieve OpenAI API Key
openai_api_key = os.getenv("OPENAI_API_KEY")

# Create OpenAI Client
client = None
if openai_api_key and not openai_api_key.startswith("your_openai_api_key"):
    client = OpenAI(api_key=openai_api_key)
else:
    print("[Warning] OPENAI_API_KEY is missing or invalid in environment variables.")

# Request and Response schemas
class ChatRequest(BaseModel):
    message: str
    response_id: str | None = None  # Previous response ID for stateful chaining

class ChatResponse(BaseModel):
    reply: str
    response_id: str
    execution_time_sec: float
    timestamp: str

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Openchat AI Responses API Server",
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "openai_connected": client is not None
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    start_time = time.time()
    
    # Check if OpenAI client is initialized
    global client
    if client is None:
        # Re-check environment in case of runtime change
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and not api_key.startswith("your_openai_api_key"):
            client = OpenAI(api_key=api_key)
        else:
            raise HTTPException(
                status_code=500,
                detail="OpenAI API Key is not configured. Please set the OPENAI_API_KEY env variable."
            )
            
    # Setup configuration parameters as requested
    instructions = " 당신은 소설 운수 좋은 날을 집필한 현진건 작가님입니다."
    vector_store_id = "vs_6a47c8ebbc988191a5c89ff6c809a267"
    tools = [
        {
            "type": "file_search",
            "vector_store_ids": [vector_store_id]
        }
    ]
    
    prev_id = request.response_id
    
    try:
        if prev_id:
            print(f"[Responses API] Chaining query with previous_response_id: {prev_id}")
            response = client.responses.create(
                model="gpt-4o",
                input=request.message,
                instructions=instructions,
                tools=tools,
                previous_response_id=prev_id
            )
        else:
            print("[Responses API] Initiating new conversation thread.")
            response = client.responses.create(
                model="gpt-4o",
                input=request.message,
                instructions=instructions,
                tools=tools
            )
            
        reply_text = response.output_text
        new_response_id = response.id
        execution_time = time.time() - start_time
        timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"[Responses API] Success. New response.id: {new_response_id}")
        
        return ChatResponse(
            reply=reply_text,
            response_id=new_response_id,
            execution_time_sec=execution_time,
            timestamp=timestamp_str
        )
        
    except Exception as e:
        print(f"[Error in Responses API Call] {e}")
        raise HTTPException(
            status_code=500,
            detail=f"OpenAI Responses API call failed: {str(e)}"
        )
