"""SRF Initialisation Script.

Run once at startup via OpenClaw exec tool. Creates workspace directories,
validates required environment variables, and registers PromptLedger prompts
(when configured). Safe to run multiple times — idempotent.

Usage (via OpenClaw exec tool):
    python scripts/srf_init.py
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Minimal structlog bootstrap so output reaches stdout/stderr in subprocess
# ---------------------------------------------------------------------------
import structlog

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
)

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Required and optional environment variables
# ---------------------------------------------------------------------------

_REQUIRED_VARS = ("SRF_LLM_PROVIDER", "SRF_LLM_MODEL", "SRF_LLM_API_KEY")
_WORKSPACE_SUBDIRS = ("newsletters", "candidates", "forum", "memory")


def _validate_env() -> None:
    """Raise SystemExit(1) if any required env var is absent."""
    missing = [v for v in _REQUIRED_VARS if not os.environ.get(v)]
    if missing:
        for var in missing:
            log.error("required environment variable not set", var=var)
        print(
            f"ERROR: Required environment variable(s) not set: {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)


def _create_workspace_dirs(workspace: Path) -> None:
    """Create workspace subdirectories if they do not already exist."""
    for name in _WORKSPACE_SUBDIRS:
        subdir = workspace / name
        subdir.mkdir(parents=True, exist_ok=True)
        log.info("workspace subdir ready", path=str(subdir))


def main() -> None:
    # 1. Validate required vars
    _validate_env()

    # 2. Resolve workspace root from OPENCLAW_WORKSPACE_DIR
    workspace = Path(os.environ.get("OPENCLAW_WORKSPACE_DIR", "/data/workspace"))
    _create_workspace_dirs(workspace)

    # 3. Build PromptLedger tracker (None when not configured)
    pl_url = os.environ.get("PROMPTLEDGER_API_URL") or None
    pl_key = os.environ.get("PROMPTLEDGER_API_KEY") or None

    tracker = None
    if pl_url and pl_key:
        try:
            from srf.config import SRFConfig
            from srf.observability import build_tracker

            config = SRFConfig(
                llm_provider=os.environ["SRF_LLM_PROVIDER"],
                llm_model=os.environ["SRF_LLM_MODEL"],
                llm_api_key=os.environ["SRF_LLM_API_KEY"],
                workspace_root=workspace,
                log_level=os.environ.get("SRF_LOG_LEVEL", "INFO"),
                promptledger_enabled=True,
                promptledger_api_url=pl_url,
                promptledger_api_key=pl_key,
                arxiv_delay_seconds=float(os.environ.get("SRF_ARXIV_DELAY_SECONDS", "3")),
                min_papers=int(os.environ.get("SRF_MIN_PAPERS", "2")),
                paper_token_budget=int(os.environ.get("SRF_PAPER_TOKEN_BUDGET", "80000")),
                max_prep_retries=int(os.environ.get("SRF_MAX_PREP_RETRIES", "3")),
            )
            tracker = build_tracker(config)
        except Exception as exc:
            log.warning("observability disabled", reason=str(exc))
    else:
        log.info("observability not configured — PROMPTLEDGER_API_URL absent, running without tracker")

    # 4. Register prompts (no-op when tracker is None)
    if tracker is not None:
        import asyncio

        from srf.observability import register_prompts
        from srf.prompts import ALL_PROMPTS

        asyncio.run(register_prompts(tracker, ALL_PROMPTS))
        log.info("prompts registered with PromptLedger", count=len(ALL_PROMPTS))

    # 5. Done
    log.info("SRF init complete", workspace=str(workspace))
    print("SRF init complete", flush=True)


if __name__ == "__main__":
    main()
