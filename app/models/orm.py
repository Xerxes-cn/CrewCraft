import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Crew(Base):
    __tablename__ = "crews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    workflow_type: Mapped[str] = mapped_column(String(50), nullable=False, default="sequential")
    workflow_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    tools: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    agents: Mapped[list["Agent"]] = relationship(
        "Agent", back_populates="crew", cascade="all, delete-orphan", order_by="Agent.order"
    )
    tasks: Mapped[list["Task"]] = relationship(
        "Task", back_populates="crew", cascade="all, delete-orphan"
    )


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crew_id: Mapped[int] = mapped_column(ForeignKey("crews.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(500), nullable=False)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tools: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    llm_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    depends_on: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)

    crew: Mapped["Crew"] = relationship("Crew", back_populates="agents")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crew_id: Mapped[int] = mapped_column(ForeignKey("crews.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    input: Mapped[str] = mapped_column(Text, nullable=False)
    messages: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    crew: Mapped["Crew"] = relationship("Crew", back_populates="tasks")
