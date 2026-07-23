"""Provider-facing chat types and the ``LLMProvider`` interface.

Providers are swappable behind this interface (PRD §6.2). The runner depends
only on these types, so the real OpenRouter client and the free ``StubProvider``
are interchangeable in tests and dry-runs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str  # "system" | "user" | "assistant"
    content: str


class ModelInfo(BaseModel):
    id: str
    name: str = ""
    context_length: int | None = None
    prompt_price: float = 0.0       # USD per token
    completion_price: float = 0.0   # USD per token


class ChatResult(BaseModel):
    """Normalized result of a single chat completion."""

    model: str
    content: str
    finish_reason: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    web_search_used: bool = False
    search_queries: list[str] = Field(default_factory=list)
    search_citations: list[str] = Field(default_factory=list)  # URLs from web-search annotations


class LLMProvider(ABC):
    """Minimal async LLM interface used by the orchestrator and runner."""

    @abstractmethod
    async def chat(
        self,
        model: str,
        messages: list[ChatMessage],
        *,
        max_tokens: int,
        temperature: float = 0.3,
        enable_web_search: bool = False,
        response_schema: dict[str, object] | None = None,
    ) -> ChatResult:
        """Run one chat completion and return a normalized result."""

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """Return the available model catalog."""

    async def aclose(self) -> None:
        """Release any underlying resources (no-op by default)."""
        return None
