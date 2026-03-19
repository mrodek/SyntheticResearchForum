"""Story 1.1.3 — Forum Staging Script acceptance tests."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path("scripts/validate_and_stage_forum.py")

_VALID_CONFIG = {
    "topic": "Attention Mechanisms in Transformers",
    "framing_question": "Do sparse attention patterns outperform dense attention?",
    "tension_axis": "sparse-vs-dense",
    "paper_refs": ["2301.00001", "2301.00002"],
    "newsletter_slug": "ml-weekly-2026-03",
    "generated_at": "2026-03-18T00:00:00Z",
    "source_papers": [],
}


def _run_script(
    config_path: str | None,
    tmp_path: Path,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    env = {**os.environ, "OPENCLAW_WORKSPACE_DIR": str(tmp_path)}
    cmd = [sys.executable, str(_SCRIPT)]
    if config_path is not None:
        cmd += ["--config-path", config_path]
    if extra_args:
        cmd += extra_args
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


# ---------------------------------------------------------------------------
# Scenario: exits 0 and writes trigger JSON to stdout for a valid config
# ---------------------------------------------------------------------------


def test_stage_exits_0_on_valid_config(tmp_path: Path) -> None:
    config_file = tmp_path / "candidate.json"
    config_file.write_text(json.dumps(_VALID_CONFIG), encoding="utf-8")

    result = _run_script(str(config_file), tmp_path)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    out = json.loads(result.stdout)
    assert "forum_id" in out
    assert "workspace_path" in out
    assert "trace_id" in out


def test_stage_writes_state_json(tmp_path: Path) -> None:
    config_file = tmp_path / "candidate.json"
    config_file.write_text(json.dumps(_VALID_CONFIG), encoding="utf-8")

    result = _run_script(str(config_file), tmp_path)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    out = json.loads(result.stdout)
    workspace = Path(out["workspace_path"])
    state_file = workspace / "state.json"
    assert state_file.exists(), "state.json not written"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["forum_status"] == "workspace_staged"


# ---------------------------------------------------------------------------
# Scenario: exits 1 when config file is not found
# ---------------------------------------------------------------------------


def test_stage_exits_1_on_missing_config(tmp_path: Path) -> None:
    result = _run_script(str(tmp_path / "nonexistent.json"), tmp_path)

    assert result.returncode == 1
    assert "config file not found" in (result.stdout + result.stderr).lower()


# ---------------------------------------------------------------------------
# Scenario: exits 1 when config JSON is malformed
# ---------------------------------------------------------------------------


def test_stage_exits_1_on_bad_json(tmp_path: Path) -> None:
    config_file = tmp_path / "bad.json"
    config_file.write_text("{not valid json", encoding="utf-8")

    result = _run_script(str(config_file), tmp_path)

    assert result.returncode == 1
    assert "invalid config" in (result.stdout + result.stderr).lower()


# ---------------------------------------------------------------------------
# Scenario: exits 1 when config has no paper_refs
# ---------------------------------------------------------------------------


def test_stage_exits_1_on_empty_paper_refs(tmp_path: Path) -> None:
    config = {**_VALID_CONFIG, "paper_refs": []}
    config_file = tmp_path / "no_papers.json"
    config_file.write_text(json.dumps(config), encoding="utf-8")

    result = _run_script(str(config_file), tmp_path)

    assert result.returncode == 1
    assert "no papers" in (result.stdout + result.stderr).lower()


# ---------------------------------------------------------------------------
# Scenario: forum_id matches forum-YYYYMMDD-{8 hex chars}
# ---------------------------------------------------------------------------


def test_stage_forum_id_matches_pattern(tmp_path: Path) -> None:
    config_file = tmp_path / "candidate.json"
    config_file.write_text(json.dumps(_VALID_CONFIG), encoding="utf-8")

    result = _run_script(str(config_file), tmp_path)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    out = json.loads(result.stdout)
    assert re.match(r"^forum-\d{8}-[0-9a-f]{8}$", out["forum_id"]), (
        f"forum_id {out['forum_id']!r} does not match expected pattern"
    )


# ---------------------------------------------------------------------------
# Scenario: stdout JSON contains a non-empty trace_id
# ---------------------------------------------------------------------------


def test_stage_trace_id_is_non_empty(tmp_path: Path) -> None:
    config_file = tmp_path / "candidate.json"
    config_file.write_text(json.dumps(_VALID_CONFIG), encoding="utf-8")

    result = _run_script(str(config_file), tmp_path)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    out = json.loads(result.stdout)
    assert out["trace_id"], "trace_id must be a non-empty string"
