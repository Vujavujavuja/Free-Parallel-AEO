"""Project-wide constants and enumerations."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

# Repo/runtime paths. PROJECT_ROOT is resolved relative to this file so it works
# regardless of the current working directory.
PACKAGE_ROOT: Path = Path(__file__).resolve().parent
PROJECT_ROOT: Path = PACKAGE_ROOT.parent.parent
CONFIG_DIR: Path = PROJECT_ROOT / "config"
DEFAULT_CONFIG_FILE: Path = CONFIG_DIR / "default.toml"
DATA_DIR: Path = PROJECT_ROOT / "data"
RUNS_DIR: Path = DATA_DIR / "runs"
WEB_DIST_DIR: Path = PACKAGE_ROOT / "web" / "dist"

API_PREFIX = "/api"


class RunStatus(StrEnum):
    """Pipeline state machine states (see PRD §4.1)."""

    CREATED = "created"
    GENERATING_QUESTIONS = "generating_questions"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING_MODELS = "running_models"
    ANALYZING = "analyzing"
    REPORTING = "reporting"
    COMPLETED = "completed"
    FAILED = "failed"


class PromptMode(StrEnum):
    SINGLE_SHOT = "single_shot"
    PER_QUESTION = "per_question"


class ReportFormat(StrEnum):
    XLSX = "xlsx"
    CSV = "csv"
    JSON = "json"


class Provenance(StrEnum):
    """How a model came to mention (or not mention) the brand (PRD §4.4 FR-20)."""

    ORGANIC = "organic"            # mentioned without searching
    SEARCH_DRIVEN = "search_driven"  # mentioned after searching
    ABSENT = "absent"             # not mentioned at all


class MentionKind(StrEnum):
    BRAND = "brand"
    COMPETITOR = "competitor"
