"""ORM models mirroring the PRD data model (§7)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aeo.constants import RunStatus
from aeo.db.base import Base, TimestampMixin, UUIDMixin


class Company(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(255))
    products: Mapped[list[Any]] = mapped_column(default=list)
    competitors: Mapped[list[Any]] = mapped_column(default=list)
    aliases: Mapped[list[Any]] = mapped_column(default=list)
    icp: Mapped[str | None] = mapped_column(Text)
    regions: Mapped[list[Any]] = mapped_column(default=list)
    notes: Mapped[str | None] = mapped_column(Text)

    runs: Mapped[list[Run]] = relationship(back_populates="company")


class Run(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "runs"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default=RunStatus.CREATED)
    stage_detail: Mapped[str | None] = mapped_column(Text)
    orchestrator_model: Mapped[str] = mapped_column(String(128))
    target_models: Mapped[list[Any]] = mapped_column(default=list)
    options: Mapped[dict[str, Any]] = mapped_column(default=dict)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column()

    company: Mapped[Company] = relationship(back_populates="runs")
    questions: Mapped[list[Question]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    responses: Mapped[list[ModelResponse]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    reports: Mapped[list[Report]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class Question(UUIDMixin, Base):
    __tablename__ = "questions"

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    index: Mapped[int] = mapped_column(Integer)
    category: Mapped[str | None] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(Text)
    expected_source_types: Mapped[list[Any]] = mapped_column(default=list)

    run: Mapped[Run] = relationship(back_populates="questions")


class ModelResponse(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "model_responses"

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    # Null for single-shot whole-answer responses.
    question_id: Mapped[str | None] = mapped_column(ForeignKey("questions.id"))
    model_id: Mapped[str] = mapped_column(String(128), index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    finish_reason: Mapped[str | None] = mapped_column(String(32))
    web_search_used: Mapped[bool] = mapped_column(Boolean, default=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)

    run: Mapped[Run] = relationship(back_populates="responses")
    citations: Mapped[list[Citation]] = relationship(
        back_populates="response", cascade="all, delete-orphan"
    )
    mentions: Mapped[list[Mention]] = relationship(
        back_populates="response", cascade="all, delete-orphan"
    )


class Citation(UUIDMixin, Base):
    __tablename__ = "citations"

    response_id: Mapped[str] = mapped_column(ForeignKey("model_responses.id"), index=True)
    domain: Mapped[str] = mapped_column(String(255), index=True)
    url: Mapped[str | None] = mapped_column(String(1024))
    question_index: Mapped[int | None] = mapped_column(Integer)
    brand_owned: Mapped[bool] = mapped_column(Boolean, default=False)

    response: Mapped[ModelResponse] = relationship(back_populates="citations")


class Mention(UUIDMixin, Base):
    __tablename__ = "mentions"

    response_id: Mapped[str] = mapped_column(ForeignKey("model_responses.id"), index=True)
    entity: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(16))  # brand | competitor
    question_index: Mapped[int | None] = mapped_column(Integer)
    count: Mapped[int] = mapped_column(Integer, default=0)

    response: Mapped[ModelResponse] = relationship(back_populates="mentions")


class Report(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reports"

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    format: Mapped[str] = mapped_column(String(16))  # xlsx | csv | json
    path: Mapped[str] = mapped_column(String(1024))

    run: Mapped[Run] = relationship(back_populates="reports")
