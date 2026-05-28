from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# --- Crew ---

class CrewCreate(BaseModel):
    name: str
    description: Optional[str] = None
    workflow_type: str = "sequential"
    workflow_config: Optional[dict] = None


class CrewUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    workflow_type: Optional[str] = None
    workflow_config: Optional[dict] = None


class CrewResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    workflow_type: str
    workflow_config: Optional[dict]
    created_at: datetime
    agents: list["AgentResponse"] = []

    class Config:
        from_attributes = True


# --- Agent ---

class AgentCreate(BaseModel):
    name: str
    role: str
    system_prompt: Optional[str] = None
    tools: Optional[list] = None
    model_config: Optional[dict] = None
    order: int = 0
    depends_on: Optional[list] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    system_prompt: Optional[str] = None
    tools: Optional[list] = None
    model_config: Optional[dict] = None
    order: Optional[int] = None
    depends_on: Optional[list] = None


class AgentResponse(BaseModel):
    id: int
    crew_id: int
    name: str
    role: str
    system_prompt: Optional[str]
    tools: Optional[list]
    model_config: Optional[dict]
    order: int
    depends_on: Optional[list]

    class Config:
        from_attributes = True


# --- Task ---

class TaskRunRequest(BaseModel):
    input: str


class TaskResponse(BaseModel):
    id: int
    crew_id: int
    status: str
    input: str
    messages: Optional[list]
    result: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
