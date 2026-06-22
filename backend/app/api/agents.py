from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.llm.manager import llm
from app.models.orm import Crew, Agent
from app.schemas.api import AgentCreate, AgentResponse, AgentUpdate, GeneratePromptRequest, GeneratePromptResponse
from app.engine.tools import Tool
from app.engine.skills import load_skills
from app.services.workspace import init_agent_workspace, remove_agent_workspace

router = APIRouter(prefix="/api", tags=["agents"])


@router.get("/skills")
async def list_skills():
    """Return all skill presets (from skills/*.md files)."""
    return load_skills()


@router.get("/tools")
async def list_tools():
    """Return all available tools with name and description for the frontend."""
    return [
        {"name": name, "description": cls.description}
        for name, cls in Tool._tools.items()
    ]


@router.post("/crews/{crew_id}/agents", response_model=AgentResponse, status_code=201)
async def create_agent(crew_id: int, data: AgentCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Crew).where(Crew.id == crew_id))
    crew = result.scalar_one_or_none()
    if not crew:
        raise HTTPException(status_code=404, detail="Crew not found")

    agent = Agent(crew_id=crew_id, **data.model_dump())
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    init_agent_workspace(crew.id, crew.name, agent.name, agent.order)
    return agent


@router.put("/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: int, data: AgentUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(agent, key, value)

    await db.commit()
    await db.refresh(agent)
    return agent


@router.post("/generate-prompt", response_model=GeneratePromptResponse)
async def generate_prompt(data: GeneratePromptRequest):
    desc = data.crew_description or "无"
    system = "你是一个AI团队的提示词专家。请根据团队信息和角色，为该智能体生成一段专业的系统提示词。直接输出提示词内容，不要包含任何解释或前缀。"

    user = f"""团队名称：{data.crew_name}
团队描述：{desc}
工作流类型：{data.workflow_type}
智能体角色：{data.role}

请生成系统提示词："""

    prompt = await llm.chat_completion(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.7,
        max_tokens=1024,
    )
    return {"prompt": prompt.strip()}


@router.delete("/agents/{agent_id}", status_code=204)
async def delete_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Load crew to get name for workspace removal
    crew_result = await db.execute(select(Crew).where(Crew.id == agent.crew_id))
    crew = crew_result.scalar_one_or_none()
    if crew:
        remove_agent_workspace(crew.id, crew.name, agent.name, agent.order)

    await db.delete(agent)
    await db.commit()
