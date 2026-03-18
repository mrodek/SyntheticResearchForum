"""Story 1.1 — Project Scaffold acceptance tests."""

import subprocess
import sys
from pathlib import Path


def test_package_importable() -> None:
    """Scenario: package is importable."""
    import srf  # noqa: F401

    assert srf.__version__


def test_env_example_documents_required_vars() -> None:
    """Scenario: .env.example documents all required variables."""
    env_example = Path(__file__).parents[2] / ".env.example"
    content = env_example.read_text()

    required = [
        "SRF_LLM_PROVIDER",
        "SRF_LLM_MODEL",
        "SRF_LLM_API_KEY",
        "PROMPTLEDGER_API_URL",
        "PROMPTLEDGER_API_KEY",
        "SRF_WORKSPACE_ROOT",
        "SRF_LOG_LEVEL",
    ]
    for var in required:
        assert var in content, f"{var} missing from .env.example"


def test_ruff_passes_on_scaffold() -> None:
    """Scenario: ruff passes on the initial scaffold."""
    src_root = Path(__file__).parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "src/", "tests/"],
        cwd=src_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"ruff errors:\n{result.stdout}\n{result.stderr}"
