"""Story 1.1.6 — update_srf skill and script acceptance tests."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

_BASH_TESTS = pytest.mark.skipif(
    sys.platform == "win32",
    reason="bash script tests run on Linux (Railway/CI) only",
)

_SKILLS_ROOT = Path("skills")
_SCRIPTS_ROOT = Path("scripts")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_skill(name: str) -> tuple[dict, str]:
    """Return (frontmatter dict, body str) for a SKILL.md file."""
    path = _SKILLS_ROOT / name / "SKILL.md"
    assert path.exists(), f"Missing skill file: {path}"
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) >= 3, f"No YAML frontmatter found in {path}"
    fm = yaml.safe_load(parts[1])
    body = parts[2]
    return fm, body


def _make_git_repo(path: Path) -> None:
    """Initialise a minimal git repo with one commit at path."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        check=True, capture_output=True, cwd=str(path),
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        check=True, capture_output=True, cwd=str(path),
    )
    (path / "README.md").write_text("test")
    subprocess.run(["git", "add", "."], check=True, capture_output=True, cwd=str(path))
    subprocess.run(
        ["git", "commit", "-m", "init"],
        check=True, capture_output=True, cwd=str(path),
    )


def _lock(path: Path) -> None:
    """Remove write permission from path recursively."""
    for p in [path, *path.rglob("*")]:
        current = p.stat().st_mode
        p.chmod(current & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def _is_writable(path: Path) -> bool:
    return os.access(path, os.W_OK)


def _run_script(tmp_path: Path, srf_dir: Path, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    script = _SCRIPTS_ROOT / "update_srf.sh"
    env = os.environ.copy()
    env["SRF_DIR"] = str(srf_dir)
    env["VENV_PIP"] = "echo pip-skipped"  # skip real pip in unit tests
    env["LOG_DIR"] = str(tmp_path / "logs")
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(script)],
        env=env,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Scenario: success path — pull succeeds, /data/srf relocked, log written
# ---------------------------------------------------------------------------


@_BASH_TESTS
def test_success_exits_zero_and_relocks(tmp_path: Path) -> None:
    srf = tmp_path / "srf"
    _make_git_repo(srf)
    _lock(srf)

    result = _run_script(tmp_path, srf)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert not _is_writable(srf), "/data/srf should be read-only after success"


@_BASH_TESTS
def test_success_writes_log_entry(tmp_path: Path) -> None:
    srf = tmp_path / "srf"
    _make_git_repo(srf)
    _lock(srf)

    _run_script(tmp_path, srf)

    log = tmp_path / "logs" / "update_srf.log"
    assert log.exists(), "Log file should be created"
    content = log.read_text()
    assert "SUCCESS" in content


@_BASH_TESTS
def test_success_stdout_contains_git_sha(tmp_path: Path) -> None:
    srf = tmp_path / "srf"
    _make_git_repo(srf)
    _lock(srf)

    result = _run_script(tmp_path, srf)

    assert result.returncode == 0
    # git SHA is 7+ hex chars
    import re
    assert re.search(r"[0-9a-f]{7,}", result.stdout), (
        f"stdout should contain git SHA, got: {result.stdout!r}"
    )


# ---------------------------------------------------------------------------
# Scenario: git pull failure — relocks and writes FAILED log entry
# ---------------------------------------------------------------------------


@_BASH_TESTS
def test_git_failure_relocks_and_logs(tmp_path: Path) -> None:
    srf = tmp_path / "srf"
    _make_git_repo(srf)
    _lock(srf)

    # Point to a non-existent remote to force pull failure
    subprocess.run(
        ["git", "remote", "add", "origin", "https://invalid.example.com/norepo.git"],
        capture_output=True, cwd=str(srf),
    )
    # Unlock so we can add the remote, then relock
    for p in [srf, *srf.rglob("*")]:
        p.chmod(p.stat().st_mode | stat.S_IWUSR)
    subprocess.run(
        ["git", "remote", "set-url", "origin", "https://invalid.example.com/norepo.git"],
        capture_output=True, cwd=str(srf),
    )
    _lock(srf)

    result = _run_script(tmp_path, srf, extra_env={"FORCE_PULL": "1"})

    assert not _is_writable(srf), "/data/srf must be relocked even after pull failure"
    log = tmp_path / "logs" / "update_srf.log"
    assert log.exists()
    assert "FAILED" in log.read_text()


# ---------------------------------------------------------------------------
# Scenario: log directory created if absent
# ---------------------------------------------------------------------------


@_BASH_TESTS
def test_creates_log_directory_if_absent(tmp_path: Path) -> None:
    srf = tmp_path / "srf"
    _make_git_repo(srf)
    _lock(srf)

    log_dir = tmp_path / "logs"
    assert not log_dir.exists()

    result = _run_script(tmp_path, srf)

    assert log_dir.exists(), "Log directory should be created by the script"
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# Scenario: SKILL.md frontmatter
# ---------------------------------------------------------------------------


def test_update_srf_skill_has_valid_frontmatter() -> None:
    fm, _ = _parse_skill("update_srf")
    assert fm.get("name") == "update_srf"
    assert len(fm.get("description", "")) >= 10, "description too short"


# ---------------------------------------------------------------------------
# Scenario: SKILL.md references update_srf.sh via exec
# ---------------------------------------------------------------------------


def test_update_srf_skill_references_script() -> None:
    _, body = _parse_skill("update_srf")
    assert "scripts/update_srf.sh" in body


def test_update_srf_skill_has_error_handling() -> None:
    _, body = _parse_skill("update_srf")
    lower = body.lower()
    assert "stderr" in lower
    assert "stop" in lower


# ---------------------------------------------------------------------------
# Scenario: SKILL.md includes /data/srf edit prohibition
# ---------------------------------------------------------------------------


def test_update_srf_skill_prohibits_srf_edits() -> None:
    _, body = _parse_skill("update_srf")
    assert "/data/srf/" in body
    lower = body.lower()
    assert "never edit" in lower or "must never edit" in lower


# ---------------------------------------------------------------------------
# Scenario: update_srf.sh exists and is executable
# ---------------------------------------------------------------------------


def test_update_srf_script_exists() -> None:
    script = _SCRIPTS_ROOT / "update_srf.sh"
    assert script.exists(), "scripts/update_srf.sh must exist"


@_BASH_TESTS
def test_update_srf_script_is_executable() -> None:
    script = _SCRIPTS_ROOT / "update_srf.sh"
    assert os.access(script, os.X_OK), "scripts/update_srf.sh must be executable"
