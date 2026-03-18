"""Story 1.5 — Span Logging Utilities acceptance tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

# ---------------------------------------------------------------------------
# Scenario: log_span returns None when tracker is None
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_span_returns_none_when_tracker_none() -> None:
    from srf.spans import log_span

    result = await log_span(
        tracker=None,
        state={},
        name="test",
        kind="llm.generation",
        status="ok",
    )
    assert result is None


# ---------------------------------------------------------------------------
# Scenario: log_span submits a SpanPayload and returns span_id when tracker provided
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_span_returns_span_id_from_tracker() -> None:
    from srf.spans import log_span

    mock_tracker = AsyncMock()
    mock_tracker.log_span = AsyncMock(return_value="span-xyz")

    result = await log_span(
        tracker=mock_tracker,
        state={"trace_id": "t1"},
        name="test",
        kind="llm.generation",
        status="ok",
    )
    assert result == "span-xyz"


# ---------------------------------------------------------------------------
# Scenario: log_span reads trace_id and parent_span_id from state dict
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_span_reads_trace_and_parent_from_state() -> None:
    from srf.spans import log_span

    captured: list = []

    async def capture_span(payload):
        captured.append(payload)
        return "span-id"

    mock_tracker = AsyncMock()
    mock_tracker.log_span = capture_span

    await log_span(
        tracker=mock_tracker,
        state={"trace_id": "trace-abc", "phase_span_id": "span-parent"},
        name="test",
        kind="llm.generation",
        status="ok",
    )

    assert len(captured) == 1
    payload = captured[0]
    assert payload.trace_id == "trace-abc"
    assert payload.parent_span_id == "span-parent"


# ---------------------------------------------------------------------------
# Scenario: log_span stores returned span_id back into state under state_key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_span_stores_span_id_in_state() -> None:
    from srf.spans import log_span

    mock_tracker = AsyncMock()
    mock_tracker.log_span = AsyncMock(return_value="new-span-id")

    state: dict = {"trace_id": "t1"}
    await log_span(
        tracker=mock_tracker,
        state=state,
        name="test",
        kind="workflow.phase",
        status="ok",
        state_key="phase_span_id",
    )

    assert state["phase_span_id"] == "new-span-id"


# ---------------------------------------------------------------------------
# Scenario: log_span is a no-op and does not raise on 5xx from PromptLedger
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_span_swallows_http_5xx_errors() -> None:
    from srf.spans import log_span

    async def raise_503(_payload):
        response = MagicMock()
        response.status_code = 503
        raise httpx.HTTPStatusError(
            "503 Service Unavailable",
            request=MagicMock(),
            response=response,
        )

    mock_tracker = AsyncMock()
    mock_tracker.log_span = raise_503

    result = await log_span(
        tracker=mock_tracker,
        state={"trace_id": "t1"},
        name="test",
        kind="llm.generation",
        status="ok",
    )
    assert result is None
