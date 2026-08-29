import re
import json
import os
from typing import List, Tuple
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, message_to_dict

def clean_youtube_url(url: str) -> str:
    """
    Extracts the standard YouTube video URL or ID.
    Supports standard, shortened (youtu.be), and embed URLs.
    """
    if not url:
        return ""
    
    # Extract video ID using regex
    pattern = r'(?:https?://)?(?:www\.)?(?:youtube\.com/(?:[^/]+/.+/|(?:v|e(?:mbed)?)/||user/(?:[^/]+)/|shorts/)|youtu\.be/)([^"&?/\s]{11})'
    match = re.search(pattern, url)
    if match:
        video_id = match.group(1)
        return f"https://www.youtube.com/watch?v={video_id}"
    return url

def format_messages_for_logging(messages: List[BaseMessage]) -> str:
    """
    Formats a list of BaseMessages into a clean string representation for log output.
    """
    formatted_logs = []
    for idx, msg in enumerate(messages):
        role = "System"
        if isinstance(msg, HumanMessage):
            role = "User"
        elif isinstance(msg, AIMessage):
            role = "AI"
        
        # Safely access msg content or convert to string if it lacks the attribute
        content = msg.content if hasattr(msg, "content") else str(msg)
        formatted_logs.append(f"[{role} - Msg {idx+1}]: {content}")
        
    return "\n".join(formatted_logs)

def get_outline(current_path: str) -> str:
    """
    Reads the outline text file from the current path.
    """
    outline_path = os.path.join(current_path, "outline.txt")
    if os.path.exists(outline_path):
        with open(outline_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def save_outline(current_path: str, content: str) -> None:
    """
    Saves the outline text file to the current path.
    """
    outline_path = os.path.join(current_path, "outline.txt")
    with open(outline_path, "w", encoding="utf-8") as f:
        f.write(content)

def save_state(current_path: str, state: dict) -> None:
    """
    Serializes and saves the agent workflow state to a JSON file.
    """
    state_path = os.path.join(current_path, "state.json")
    
    # Serialize messages list
    serialized_messages = []
    for msg in state.get("messages", []):
        if hasattr(msg, "to_json"):
            try:
                serialized_messages.append(message_to_dict(msg))
            except Exception:
                serialized_messages.append({
                    "type": "human" if "Human" in type(msg).__name__ else "ai",
                    "data": {"content": str(msg.content if hasattr(msg, "content") else msg)}
                })
        elif isinstance(msg, dict):
            serialized_messages.append(msg)
        else:
            serialized_messages.append({
                "type": "unknown",
                "data": {"content": str(msg)}
            })
            
    # Serialize task history
    serialized_tasks = []
    for task in state.get("task_history", []):
        if hasattr(task, "dict"):
            serialized_tasks.append(task.dict())
        else:
            serialized_tasks.append(dict(task))
            
    # Serialize references
    references = state.get("references", {"queries": [], "docs": []})
    serialized_refs = {
        "queries": list(references.get("queries", [])),
        "docs": []
    }
    for doc in references.get("docs", []):
        serialized_refs["docs"].append({
            "page_content": getattr(doc, "page_content", str(doc)),
            "metadata": getattr(doc, "metadata", {})
        })
        
    data = {
        "messages": serialized_messages,
        "task_history": serialized_tasks,
        "references": serialized_refs
    }
    
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_state(current_path: str) -> dict:
    """
    Deserializes and loads the agent workflow state from a JSON file.
    """
    state_path = os.path.join(current_path, "state.json")
    if not os.path.exists(state_path):
        return None
        
    try:
        from langchain_core.messages import messages_from_dict
        from langchain_core.documents import Document
        from models import Task
        
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Deserialize messages
        messages = messages_from_dict(data.get("messages", []))
        
        # Deserialize task history
        task_history = []
        for task_dict in data.get("task_history", []):
            task_history.append(Task(**task_dict))
            
        # Deserialize references
        raw_references = data.get("references", {"queries": [], "docs": []})
        references = {
            "queries": list(raw_references.get("queries", [])),
            "docs": [],
            "last_added_time": raw_references.get("last_added_time", "최근 추가 이력 없음")
        }
        for doc_dict in raw_references.get("docs", []):
            references["docs"].append(Document(
                page_content=doc_dict.get("page_content", ""),
                metadata=doc_dict.get("metadata", {})
            ))
            
        return {
            "messages": messages,
            "task_history": task_history,
            "references": references
        }
    except Exception as e:
        print(f"[ERROR] Failed to load state: {e}")
        return None