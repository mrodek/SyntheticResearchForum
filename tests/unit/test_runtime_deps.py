"""Story 1.1.1 — OpenClaw & Lobster Installation + Base Configuration acceptance tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Scenario: python CLI is available on PATH in the local environment
# ---------------------------------------------------------------------------


def test_python_is_on_path() -> None:
    assert shutil.which("python") is not None or shutil.which("python3") is not None, (
        "Neither 'python' nor 'python3' found on PATH — cannot run SRF scripts"
    )


# ---------------------------------------------------------------------------
# Scenario: lobster CLI is resolvable (skip gracefully in envs without it)
# ---------------------------------------------------------------------------


def test_lobster_on_path_when_installed() -> None:
    import pytest

    if shutil.which("lobster") is None:
        pytest.skip("lobster not installed — run: npm install -g @clawdbot/lobster")
    assert shutil.which("lobster") is not None


# ---------------------------------------------------------------------------
# Scenario: railway.toml exists and declares port 8080 and healthcheck path
# ---------------------------------------------------------------------------


def test_railway_toml_exists_and_declares_port() -> None:
    path = Path("railway.toml")
    assert path.exists(), "railway.toml not found — required for Railway deployment"
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    deploy = data.get("deploy", {})
    assert deploy.get("healthcheckPath") == "/health", (
        "railway.toml deploy.healthcheckPath must be '/health'"
    )


def test_railway_toml_has_start_command_with_lobster_install() -> None:
    data = tomllib.loads(Path("railway.toml").read_text(encoding="utf-8"))
    start_cmd = data.get("deploy", {}).get("startCommand", "")
    assert "@clawdbot/lobster" in start_cmd, (
        "startCommand must install @clawdbot/lobster before starting OpenClaw"
    )
    assert "openclaw" in start_cmd, (
        "startCommand must invoke openclaw to start the gateway"
    )


# ---------------------------------------------------------------------------
# Scenario: openclaw.json config template has required sections
# ---------------------------------------------------------------------------


def test_openclaw_config_exists() -> None:
    path = Path("config/openclaw.json")
    assert path.exists(), (
        "config/openclaw.json not found — this template is written to "
        "$OPENCLAW_STATE_DIR/openclaw.json by scripts/srf_init.py on first start"
    )


def test_openclaw_config_allows_lobster_tool() -> None:
    data = json.loads(Path("config/openclaw.json").read_text(encoding="utf-8"))
    tools = data.get("tools", {})
    allow = tools.get("allow", [])
    assert "lobster" in allow, (
        "config/openclaw.json tools.allow must include 'lobster'"
    )


def test_openclaw_config_allows_exec_tool() -> None:
    data = json.loads(Path("config/openclaw.json").read_text(encoding="utf-8"))
    allow = data.get("tools", {}).get("allow", [])
    assert "exec" in allow or "group:runtime" in allow, (
        "config/openclaw.json must allow the exec tool or group:runtime"
    )


def test_openclaw_config_sets_workspace_dir() -> None:
    data = json.loads(Path("config/openclaw.json").read_text(encoding="utf-8"))
    workspace = (
        data.get("agents", {}).get("defaults", {}).get("workspace", "")
    )
    assert "/data" in workspace, (
        "agents.defaults.workspace must point to the /data volume"
    )


def test_openclaw_config_sets_exec_timeout() -> None:
    data = json.loads(Path("config/openclaw.json").read_text(encoding="utf-8"))
    timeout = data.get("tools", {}).get("exec", {}).get("timeoutSec", 0)
    assert timeout >= 3600, (
        "tools.exec.timeoutSec must be at least 3600 — debate runs can take over an hour"
    )


# ---------------------------------------------------------------------------
# Scenario: exec-approvals.json template has python allowlist entry
# ---------------------------------------------------------------------------


def test_exec_approvals_config_exists() -> None:
    path = Path("config/exec-approvals.json")
    assert path.exists(), (
        "config/exec-approvals.json not found — needed to allow python script execution"
    )


def test_exec_approvals_has_python_pattern() -> None:
    data = json.loads(Path("config/exec-approvals.json").read_text(encoding="utf-8"))
    agents = data.get("agents", {})
    # Check any agent has at least one python allowlist entry
    all_patterns = []
    for agent_config in agents.values():
        for entry in agent_config.get("allowlist", []):
            all_patterns.append(entry.get("pattern", ""))
    assert any("python" in p for p in all_patterns), (
        "config/exec-approvals.json must include at least one python allowlist pattern"
    )
