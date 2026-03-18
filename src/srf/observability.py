"""SRF observability — optional PromptLedger tracker with graceful degradation."""

from __future__ import annotations

import structlog

from srf.config import SRFConfig

logger = structlog.get_logger(__name__)


def build_tracker(config: SRFConfig) -> object | None:
    """Return an AsyncPromptLedgerClient if PromptLedger is configured, else None.

    Never raises. If the SDK is missing or instantiation fails, logs a WARNING
    and returns None so the system runs without observability.
    """
    if not config.promptledger_enabled:
        return None

    try:
        from promptledger_client import AsyncPromptLedgerClient  # type: ignore[import]

        return AsyncPromptLedgerClient(
            base_url=config.promptledger_api_url,
            api_key=config.promptledger_api_key,
        )
    except Exception as exc:
        logger.warning(
            "observability disabled",
            reason=str(exc),
            detail="PromptLedger client failed to initialise — observability disabled",
        )
        return None


async def register_prompts(tracker: object | None, prompts: list) -> None:
    """Register code prompts with PromptLedger.

    No-op when tracker is None. Pass tracker=None in all unit tests.
    """
    if tracker is None:
        return

    await tracker.register_code_prompts(prompts)
