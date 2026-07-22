"""LLM providers (OpenRouter + a free stub for testing)."""

from __future__ import annotations

from aeo.providers.base import (
    ChatMessage,
    ChatResult,
    LLMProvider,
    ModelInfo,
)
from aeo.providers.stub import StubProvider
from aeo.settings import Settings


def get_provider(name: str = "openrouter", settings: Settings | None = None) -> LLMProvider:
    """Construct a provider by name. ``"stub"`` runs offline at zero cost."""
    if name == "stub":
        return StubProvider()
    if name == "openrouter":
        from aeo.providers.openrouter import OpenRouterProvider

        return OpenRouterProvider(settings)
    raise ValueError(f"Unknown provider {name!r} (expected 'openrouter' or 'stub').")


__all__ = [
    "ChatMessage",
    "ChatResult",
    "LLMProvider",
    "ModelInfo",
    "StubProvider",
    "get_provider",
]
