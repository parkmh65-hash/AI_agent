from pydantic import BaseModel, Field

class Task(BaseModel):
    agent: str = Field(description="The agent to execute next: content_strategist (목차 구성 및 편집), communicator (사용자 대화 및 보고), vector_search_agent (벡터 DB에서 관련 정보 검색), 또는 web_search_agent (벡터 DB 정보가 부족하거나 최신 정보가 필요하여 인터넷/웹 검색을 통해 정보를 확보하고 벡터 DB에 추가할 때 사용)")
    done: bool = Field(default=False, description="Whether the task is completed")
    description: str = Field(description="Description of the task to be performed")
    done_at: str = Field(default="", description="Timestamp when the task was completed")
