from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore
from supabase import create_client
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Define the state structure
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    context: str

# Define the Retrieve Node function
def retrieve_node(state: AgentState):
    """
    Retrieves relevant documents from Supabase Vector Store.
    Gracefully falls back to standard LLM call if DB configuration is missing or errors out.
    """
    last_message = state["messages"][-1].content
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    # Check if Supabase credentials are set
    if (not supabase_url or not supabase_key or 
        supabase_url == "your_supabase_url_here" or 
        supabase_key == "your_supabase_anon_key_here"):
        # Graceful fallback: return a warning as context
        return {"context": "[안내: Supabase 벡터 DB 설정이 누락되었습니다. 일반 AI 모델 지식으로만 답변합니다.]"}
        
    try:
        # Connect to Supabase
        supabase = create_client(supabase_url, supabase_key)
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small", dimensions=768)
        
        # Load Vector Store
        vector_store = SupabaseVectorStore(
            client=supabase,
            embedding=embeddings,
            table_name="documents",
            query_name="match_documents"
        )
        
        # Perform similarity search
        retrieved_docs = vector_store.similarity_search(last_message, k=3)
        context_text = "\n\n".join([doc.page_content for doc in retrieved_docs])
        
        if not context_text.strip():
            context_text = "[안내: 검색된 벡터 DB 정보가 없습니다. 일반 지식으로 답변합니다.]"
            
        return {"context": context_text}
    except Exception as e:
        # Fallback gracefully in case of database exception (e.g. pgvector not enabled)
        return {"context": f"[안내: Supabase 벡터 DB 검색 중 오류가 발생하여 일반 지식으로 답변합니다. 에러: {str(e)}]"}

# Define the Assistant Node function
def assistant_node(state: AgentState):
    """
    Generates an answer using Gemini, taking retrieved context into account if available.
    """
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash")
    
    context = state.get("context", "")
    last_message = state["messages"][-1].content
    
    # Format the prompt depending on whether we got real context or a fallback message
    if context and not context.startswith("[안내"):
        prompt = f"""You are a helpful AI assistant. Use the following context from the database to answer the user's question.
If you don't know the answer based on the context, just say that you don't know.

Context:
{context}

Question: {last_message}
Answer (in Korean):"""
    else:
        # Include the system info/error context if relevant for diagnostics
        prompt = f"""You are a helpful AI assistant.
System Notice: {context}

Question: {last_message}
Answer (in Korean):"""
    
    # Invoke Gemini with the structured prompt
    response = llm.invoke([HumanMessage(content=prompt)])
    
    # Return the assistant's reply to the message history
    return {"messages": [response]}

# Build the LangGraph StateGraph workflow
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("assistant", assistant_node)

# Connect edges
workflow.add_edge(START, "retrieve")
workflow.add_edge("retrieve", "assistant")
workflow.add_edge("assistant", END)

# Compile the graph
agent = workflow.compile()
