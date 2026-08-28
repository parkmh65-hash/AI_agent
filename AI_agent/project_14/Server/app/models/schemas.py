from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of the message author: 'user' or 'assistant'")
    content: str = Field(..., description="Content of the message")

class QueryRequest(BaseModel):
    query: str = Field(..., description="The search query or question")
    history: Optional[List[ChatMessage]] = Field(default=None, description="Conversational history for chat context")
    top_k: Optional[int] = Field(default=5, description="Number of results to retrieve")
    filter_dict: Optional[Dict[str, Any]] = Field(default=None, description="Metadata key-value filter")
    use_multiquery: Optional[bool] = Field(default=True, description="Whether to use MultiQuery LLM generation")

class SourceMetadata(BaseModel):
    source: str
    page: Any
    type: str
    original_path: str
    caption: str

class QueryResultSource(BaseModel):
    content: str
    metadata: SourceMetadata
    distance: float

class PerformanceMetrics(BaseModel):
    rows_retrieved: int = Field(..., description="Number of rows retrieved from vector store")
    retrieval_time_ms: float = Field(..., description="Time taken to search vectors in milliseconds")
    total_time_ms: float = Field(..., description="Total pipeline response time in milliseconds")

class QueryResponse(BaseModel):
    answer: str = Field(..., description="LLM generated answer based on documents")
    sources: List[QueryResultSource] = Field(..., description="The source documents retrieved and used")
    performance: PerformanceMetrics = Field(..., description="Execution speed and row count metrics")
