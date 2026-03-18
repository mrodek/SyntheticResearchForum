"""Story 1.3 — Structured Logging acceptance tests."""

from __future__ import annotations

import ast
import io
import json
from pathlib import Path

import pytest


def test_configure_logging_produces_json_at_configured_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scenario: configure_logging produces JSON output at the configured level."""
    from srf.logging import configure_logging, get_logger

    monkeypatch.setenv("SRF_LOG_LEVEL", "WARNING")
    buf = io.StringIO()
    configure_logging(level="WARNING", stream=buf)

    log = get_logger("test.component")
    log.warning("something happened", extra_key="value")

    output = buf.getvalue().strip()
    assert output, "Expected log output but got nothing"
    data = json.loads(output)
    assert "level" in data
    assert "event" in data
    assert "timestamp" in data


def test_debug_suppressed_at_info_level(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario: DEBUG events are suppressed when log level is INFO."""
    from srf.logging import configure_logging, get_logger

    buf = io.StringIO()
    configure_logging(level="INFO", stream=buf)

    log = get_logger("test.component")
    log.debug("this should not appear")

    assert buf.getvalue() == "", "DEBUG event should be suppressed at INFO level"


def test_get_logger_binds_component_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario: get_logger returns a logger bound with component name."""
    from srf.logging import configure_logging, get_logger

    buf = io.StringIO()
    configure_logging(level="DEBUG", stream=buf)

    log = get_logger("lobster.phase")
    log.info("test event")

    output = buf.getvalue().strip()
    data = json.loads(output)
    assert data.get("component") == "lobster.phase"


def test_bind_context_attaches_forum_id() -> None:
    """Scenario: bind_context attaches forum_id to all subsequent log calls."""
    from srf.logging import bind_context, configure_logging, get_logger

    buf = io.StringIO()
    configure_logging(level="DEBUG", stream=buf)

    log = get_logger("test.component")
    bind_context(forum_id="forum-abc")
    log.info("bound event")

    output = buf.getvalue().strip()
    assert output, "Expected log output"
    # Find the line that contains our event
    for line in output.splitlines():
        data = json.loads(line)
        if data.get("event") == "bound event":
            assert data.get("forum_id") == "forum-abc"
            return
    pytest.fail("Log line with 'bound event' not found")


def test_no_print_calls_in_src() -> None:
    """Scenario: no print() calls reach production log paths."""
    src_dir = Path(__file__).parents[2] / "src" / "srf"
    violations: list[str] = []

    for py_file in src_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"
            ):
                violations.append(f"{py_file}:{node.lineno}")

    assert not violations, "print() calls found in src/srf/:\n" + "\n".join(violations)
