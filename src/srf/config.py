"""SRF configuration — validates environment variables at startup."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_PROVIDERS: frozenset[str] = frozenset({"anthropic", "openai"})

_VALID_LOG_LEVELS: frozenset[str] = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


class ConfigurationError(ValueError):
    """Raised when required environment configuration is missing or invalid."""


@dataclass(frozen=True)
class SRFConfig:
    llm_provider: str
    llm_model: str
    llm_api_key: str
    workspace_root: Path
    log_level: str
    promptledger_enabled: bool
    promptledger_api_url: str | None
    promptledger_api_key: str | None
    arxiv_delay_seconds: float
    min_papers: int

    @classmethod
    def from_env(cls) -> SRFConfig:
        """Build an SRFConfig from environment variables.

        Raises ConfigurationError for any missing or invalid required value.
        """
        provider = _require("SRF_LLM_PROVIDER")
        if provider not in SUPPORTED_PROVIDERS:
            raise ConfigurationError(
                f"SRF_LLM_PROVIDER={provider!r} is not supported. "
                f"Supported values: {sorted(SUPPORTED_PROVIDERS)}"
            )

        model = _require("SRF_LLM_MODEL")
        api_key = _require("SRF_LLM_API_KEY")

        workspace_root = Path(os.environ.get("SRF_WORKSPACE_ROOT", "/data/workspace"))

        log_level_raw = os.environ.get("SRF_LOG_LEVEL", "INFO").upper()

        pl_url = os.environ.get("PROMPTLEDGER_API_URL") or None
        pl_key = os.environ.get("PROMPTLEDGER_API_KEY") or None

        if bool(pl_url) != bool(pl_key):
            raise ConfigurationError(
                "PROMPTLEDGER_API_URL and PROMPTLEDGER_API_KEY must both be set or both omitted."
            )

        arxiv_delay_seconds = float(os.environ.get("SRF_ARXIV_DELAY_SECONDS", "3"))
        min_papers = int(os.environ.get("SRF_MIN_PAPERS", "2"))

        return cls(
            llm_provider=provider,
            llm_model=model,
            llm_api_key=api_key,
            workspace_root=workspace_root,
            log_level=log_level_raw,
            promptledger_enabled=bool(pl_url and pl_key),
            promptledger_api_url=pl_url,
            promptledger_api_key=pl_key,
            arxiv_delay_seconds=arxiv_delay_seconds,
            min_papers=min_papers,
        )


def _require(var: str) -> str:
    value = os.environ.get(var)
    if not value:
        raise ConfigurationError(f"Required environment variable {var!r} is not set.")
    return value
