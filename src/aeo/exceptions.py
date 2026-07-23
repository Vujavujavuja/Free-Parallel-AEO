"""Typed exception hierarchy for Parallel-AEO."""

from __future__ import annotations


class AEOError(Exception):
    """Base class for all application errors."""


class ConfigurationError(AEOError):
    """Missing or invalid configuration (e.g. no OPENROUTER_API_KEY)."""


class ProviderError(AEOError):
    """An LLM provider (OpenRouter) call failed after retries."""


class ModelNotFoundError(ProviderError):
    """A requested model id is not present in the live catalog."""

    def __init__(self, model_id: str, suggestion: str | None = None) -> None:
        self.model_id = model_id
        self.suggestion = suggestion
        msg = f"Model {model_id!r} was not found in the OpenRouter catalog."
        if suggestion:
            msg += f" Did you mean {suggestion!r}?"
        super().__init__(msg)


class CostCapExceededError(AEOError):
    """The run's spend reached COST_CAP_USD and was aborted gracefully."""

    def __init__(self, spent: float, cap: float) -> None:
        self.spent = spent
        self.cap = cap
        super().__init__(f"Cost cap exceeded: spent ${spent:.4f} of ${cap:.2f} cap.")


class OrchestratorError(AEOError):
    """The orchestrator failed to produce a valid question set."""


class RunNotFoundError(AEOError):
    """A run id does not exist."""


class CompanyNotFoundError(AEOError):
    """A company id does not exist."""


class PipelineError(AEOError):
    """A pipeline stage failed irrecoverably."""
