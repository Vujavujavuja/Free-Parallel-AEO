"""Application settings.

Precedence (highest first): constructor args > environment / .env >
``config/default.toml`` > hard-coded field defaults. Secrets (the OpenRouter key,
optional API token) come only from the environment and are never read from TOML.
"""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from aeo.constants import DEFAULT_CONFIG_FILE, PROJECT_ROOT, PromptMode

# Maps flat Settings field names -> (toml_section, toml_key). Anything not listed
# here (secrets) is env-only.
_TOML_FIELD_MAP: dict[str, tuple[str, str]] = {
    "host": ("app", "host"),
    "port": ("app", "port"),
    "log_level": ("app", "log_level"),
    "data_dir": ("app", "data_dir"),
    "orchestrator_model": ("orchestrator", "model"),
    "question_count": ("orchestrator", "question_count"),
    "prompt_mode": ("run", "prompt_mode"),
    "enable_web_search": ("run", "enable_web_search"),
    "max_tokens": ("run", "max_tokens"),
    "concurrency": ("run", "concurrency"),
    "cost_cap_usd": ("run", "cost_cap_usd"),
    "auto_approve_questions": ("run", "auto_approve_questions"),
    "max_continuations": ("run", "max_continuations"),
    "ai_insights": ("run", "ai_insights"),
    "openrouter_base_url": ("openrouter", "base_url"),
    "openrouter_http_referer": ("openrouter", "http_referer"),
    "openrouter_x_title": ("openrouter", "x_title"),
    "openrouter_timeout_seconds": ("openrouter", "timeout_seconds"),
    "openrouter_max_retries": ("openrouter", "max_retries"),
    "target_models": ("panel", "targets"),
}


class _TomlDefaultsSource(PydanticBaseSettingsSource):
    """Settings source that reads flattened defaults from ``config/default.toml``."""

    def __init__(self, settings_cls: type[BaseSettings], path: Path) -> None:
        super().__init__(settings_cls)
        self._data: dict[str, Any] = {}
        if path.is_file():
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
            for field, (section, key) in _TOML_FIELD_MAP.items():
                if section in raw and key in raw[section]:
                    self._data[field] = raw[section][key]

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return self._data.get(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        return dict(self._data)


class Settings(BaseSettings):
    """Runtime configuration. See PRD §14."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- secret (env only) ---
    openrouter_api_key: SecretStr = Field(default=SecretStr(""))
    api_token: SecretStr | None = Field(default=None)

    # --- server ---
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"

    # --- orchestrator ---
    orchestrator_model: str = "anthropic/claude-opus-4.8"
    question_count: int = 10

    # --- run options ---
    prompt_mode: PromptMode = PromptMode.SINGLE_SHOT
    enable_web_search: bool = False
    max_tokens: int = 8000
    concurrency: int = 6
    cost_cap_usd: float = 5.0
    auto_approve_questions: bool = True
    max_continuations: int = 4
    ai_insights: bool = True

    # --- persistence: runs are stored as folders on disk (see aeo.storage) ---
    data_dir: str = "./data"

    # --- openrouter client ---
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_http_referer: str = "https://github.com/nvujic2002/Free-Parallel-AEO"
    openrouter_x_title: str = "Free-Parallel-AEO"
    openrouter_timeout_seconds: float = 120.0
    openrouter_max_retries: int = 4

    # --- default fan-out panel ---
    target_models: list[str] = Field(default_factory=list)

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, v: str) -> str:
        return v.upper()

    @property
    def has_api_key(self) -> bool:
        return bool(self.openrouter_api_key.get_secret_value())

    @property
    def data_path(self) -> Path:
        """Root directory for on-disk run storage."""
        return Path(self.data_dir).expanduser()

    @property
    def runs_path(self) -> Path:
        """Directory holding one folder per run."""
        return self.data_path / "runs"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Order = priority (first wins). TOML sits below env/.env but above
        # hard-coded field defaults.
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            _TomlDefaultsSource(settings_cls, DEFAULT_CONFIG_FILE),
            file_secret_settings,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    return Settings()


def _upsert_env_var(name: str, value: str) -> None:
    """Insert/replace ``name=value`` in the project ``.env`` (created if absent)."""
    env = PROJECT_ROOT / ".env"
    lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    out: list[str] = []
    found = False
    for line in lines:
        if line.strip().startswith(f"{name}="):
            out.append(f"{name}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{name}={value}")
    env.write_text("\n".join(out) + "\n", encoding="utf-8")


def update_openrouter_key(key: str) -> None:
    """Set the OpenRouter key on the running settings and persist it to .env.

    The key is stored only in the local ``.env`` (gitignored) and the in-memory
    ``SecretStr`` — never logged, and never returned by the API.
    """
    settings = get_settings()
    settings.openrouter_api_key = SecretStr(key)
    _upsert_env_var("OPENROUTER_API_KEY", key)
