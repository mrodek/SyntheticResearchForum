"""Story 6B.4 — Debate bridge script.

Reads agent preparation output from stdin, writes agents to state.json,
calls prepare_debate_context, triggers the run_forum_debate OpenClaw skill
session, polls for the DEBATE_CLOSED sentinel, validates the transcript,
and writes output JSON to stdout for Lobster.

Usage (Lobster):
    python scripts/run_debate_bridge.py
    stdin:  $agent_preparation.json
    stdout: { forum_id, workspace_path, transcript_path, turn_count, debate_status }

Exit codes:
    0 — success
    1 — DebateBridgeError; details in stderr
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

_SENTINEL = "DEBATE_CLOSED"
_DEFAULT_POLL_TIMEOUT = 600   # seconds
_DEFAULT_POLL_INTERVAL = 10.0  # seconds
_DEFAULT_MAX_TOTAL_TURNS = 30
_DEFAULT_MAX_TURNS_PER_AGENT = 8
_DEFAULT_MAX_ROUNDS = 4


# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------


class DebateBridgeError(RuntimeError):
    """Raised when the debate bridge cannot complete successfully."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_bridge(
    stdin_data: dict[str, Any],
    *,
    workspace_root: Path,
    openclaw_url: str,
    openclaw_token: str,
    poll_timeout_seconds: int = _DEFAULT_POLL_TIMEOUT,
    poll_interval_seconds: float = _DEFAULT_POLL_INTERVAL,
    tracker: object | None = None,
) -> dict[str, Any]:
    """Run the debate bridge.

    Args:
        stdin_data:            Parsed JSON from Lobster stdin ($agent_preparation.json).
        workspace_root:        Root workspace directory.
        openclaw_url:          OpenClaw gateway base URL.
        openclaw_token:        OPENCLAW_GATEWAY_TOKEN for Authorization header.
        poll_timeout_seconds:  Max seconds to wait for DEBATE_CLOSED sentinel.
        poll_interval_seconds: Seconds between transcript poll attempts.
        tracker:               PromptLedger tracker or None.

    Returns:
        Output dict for Lobster stdout.

    Raises:
        DebateBridgeError: on timeout, transcript validation failure, or API error.
    """
    forum_id = stdin_data["forum_id"]
    workspace_path = workspace_root / "forum" / forum_id

    # 1. Write agents and limits to state.json so prepare_debate_context can read them
    _update_state(workspace_path, stdin_data)

    # 2. Prepare debate_context.json
    from scripts.prepare_debate_context import DebateContextError, prepare_debate_context

    try:
        context_path = prepare_debate_context(forum_id, workspace_root)
    except DebateContextError as exc:
        raise DebateBridgeError(f"Failed to prepare debate context: {exc}") from exc

    # 3. Trigger OpenClaw skill session
    _trigger_openclaw(openclaw_url, openclaw_token, context_path)

    # 4. Poll for DEBATE_CLOSED sentinel
    transcript_path = workspace_path / "transcripts" / "transcript.jsonl"
    _poll_for_sentinel(transcript_path, poll_timeout_seconds, poll_interval_seconds)

    # 5. Validate transcript
    from scripts.validate_transcript import TranscriptError, validate_transcript

    try:
        summary = validate_transcript(transcript_path)
    except TranscriptError as exc:
        raise DebateBridgeError(f"Transcript validation failed: {exc}") from exc

    # 6. Submit phase-level span to PromptLedger (best-effort, tracker=None graceful)
    _submit_phase_span(tracker, forum_id, summary)

    return {
        **stdin_data,
        "transcript_path": str(transcript_path),
        "turn_count": summary.turn_count,
        "debate_status": summary.debate_status,
        "close_reason": summary.close_reason,
        "forum_status": "debate_complete",
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _update_state(workspace_path: Path, stdin_data: dict[str, Any]) -> None:
    """Write agents roster and debate limits into state.json."""
    state_path = workspace_path / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise DebateBridgeError(f"Cannot read state.json at {state_path}: {exc}") from exc

    state["agents"] = stdin_data.get("agents", [])
    state["max_total_turns"] = int(os.environ.get("SRF_MAX_TOTAL_TURNS", _DEFAULT_MAX_TOTAL_TURNS))
    state["max_turns_per_agent"] = int(os.environ.get("SRF_MAX_TURNS_PER_AGENT", _DEFAULT_MAX_TURNS_PER_AGENT))
    state["max_rounds"] = int(os.environ.get("SRF_MAX_ROUNDS", _DEFAULT_MAX_ROUNDS))

    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _trigger_openclaw(url: str, token: str, context_path: Path) -> None:
    """POST to OpenClaw gateway to trigger the run_forum_debate skill."""
    endpoint = f"{url.rstrip('/')}/hooks/agent"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"message": f"/run_forum_debate context_path={context_path}"}

    try:
        response = requests.post(endpoint, json=body, headers=headers, timeout=30)
    except requests.RequestException as exc:
        raise DebateBridgeError(f"Failed to reach OpenClaw at {endpoint}: {exc}") from exc

    if not response.ok:
        raise DebateBridgeError(
            f"OpenClaw returned {response.status_code} when triggering debate skill. "
            f"Response: {response.text[:200]}"
        )


def _poll_for_sentinel(
    transcript_path: Path,
    timeout_seconds: int,
    interval_seconds: float,
) -> None:
    """Poll transcript.jsonl until DEBATE_CLOSED sentinel appears or timeout."""
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        if transcript_path.exists():
            content = transcript_path.read_text(encoding="utf-8")
            if _SENTINEL in content:
                return
        time.sleep(interval_seconds)

    raise DebateBridgeError(
        f"Timeout waiting for debate to close after {timeout_seconds}s. "
        f"Transcript sentinel '{_SENTINEL}' not found at {transcript_path}."
    )


def _submit_phase_span(tracker: object | None, forum_id: str, summary: Any) -> None:
    """Submit a phase-level span to PromptLedger. Fire-and-forget — never raises."""
    if tracker is None:
        return
    try:
        import asyncio

        from srf.spans import SpanPayload

        asyncio.run(tracker.log_span(SpanPayload(  # type: ignore[attr-defined]
            trace_id=forum_id,
            name="debate",
            kind="workflow.phase",
            status="ok",
            metadata={
                "turn_count": summary.turn_count,
                "close_reason": summary.close_reason,
            },
        )))
    except Exception:  # noqa: BLE001
        pass  # observability failure must never abort the pipeline


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    import logging

    import structlog

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    )
    log = structlog.get_logger(__name__)

    try:
        stdin_data = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"ERROR: could not parse stdin JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    workspace_root = Path(os.environ.get("OPENCLAW_WORKSPACE_DIR", "/data/workspace"))
    openclaw_url = os.environ.get("OPENCLAW_GATEWAY_URL", "http://localhost:8080")
    openclaw_token = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "")

    try:
        from srf.config import SRFConfig
        from srf.observability import build_tracker
        config = SRFConfig.from_env()
        tracker = build_tracker(config)
    except Exception:  # noqa: BLE001
        tracker = None

    try:
        result = run_bridge(
            stdin_data,
            workspace_root=workspace_root,
            openclaw_url=openclaw_url,
            openclaw_token=openclaw_token,
            poll_timeout_seconds=int(os.environ.get("SRF_DEBATE_POLL_TIMEOUT", _DEFAULT_POLL_TIMEOUT)),
            poll_interval_seconds=float(os.environ.get("SRF_DEBATE_POLL_INTERVAL", _DEFAULT_POLL_INTERVAL)),
            tracker=tracker,
        )
        print(json.dumps(result))
    except DebateBridgeError as exc:
        log.error("debate bridge failed", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
