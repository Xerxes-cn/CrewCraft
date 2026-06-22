from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# --- Agent ---

class AgentCreate(BaseModel):
    name: str
    role: str
    system_prompt: Optional[str] = None
    tools: Optional[list] = None
    llm_config: Optional[dict] = None
    order: int = 0
    depends_on: Optional[list] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    system_prompt: Optional[str] = None
    tools: Optional[list] = None
    llm_config: Optional[dict] = None
    order: Optional[int] = None
    depends_on: Optional[list] = None


class AgentResponse(BaseModel):
    id: int
    name: str
    role: str
    system_prompt: Optional[str]
    tools: Optional[list]
    llm_config: Optional[dict]
    order: int
    depends_on: Optional[list]

    class Config:
        from_attributes = True


# --- Task ---

class TaskRunRequest(BaseModel):
    input: str


class TaskResponse(BaseModel):
    id: int
    status: str
    input: str
    messages: Optional[list]
    result: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
