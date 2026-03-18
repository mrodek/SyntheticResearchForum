"""SRF span logging utilities — build and submit SpanPayload objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class SpanPayload:
    """Minimal SpanPayload compatible with the PromptLedger SDK model."""

    trace_id: str
    name: str
    kind: str
    status: str
    start_time: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    parent_span_id: str | None = None
    agent_id: str | None = None
    duration_ms: int | None = None
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    prompt_name: str | None = None
    input_data: dict[str, Any] | None = None
    attributes: dict[str, Any] | None = None


async def log_span(
    *,
    tracker: object | None,
    state: dict[str, Any],
    name: str,
    kind: str,
    status: str,
    state_key: str | None = None,
    **extra: Any,
) -> str | None:
    """Build and submit a SpanPayload, returning the span_id or None.

    - Returns None immediately when tracker is None (unit-test safe).
    - Reads trace_id and parent_span_id from state.
    - Stores the returned span_id back into state[state_key] when state_key is given.
    - Swallows httpx.HTTPStatusError (5xx) so observability never interrupts a workflow.
    """
    if tracker is None:
        return None

    payload = SpanPayload(
        trace_id=state.get("trace_id", ""),
        parent_span_id=state.get("phase_span_id"),
        name=name,
        kind=kind,
        status=status,
        **extra,
    )

    try:
        span_id: str = await tracker.log_span(payload)
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "span submission failed — observability degraded",
            status_code=exc.response.status_code,
            span_name=name,
        )
        return None

    if state_key is not None:
        state[state_key] = span_id

    return span_id


