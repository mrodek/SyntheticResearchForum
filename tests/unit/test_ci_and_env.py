"""Story 1.1.5 — CI Pipeline & Deployment Documentation acceptance tests."""

from __future__ import annotations

from pathlib import Path

import yaml

_CI_PATH = Path(".github/workflows/ci.yml")
_ENV_EXAMPLE = Path(".env.example")

_REQUIRED_SRF_VARS = (
    "SRF_LLM_PROVIDER",
    "SRF_LLM_MODEL",
    "SRF_LLM_API_KEY",
    "PROMPTLEDGER_API_URL",
    "PROMPTLEDGER_API_KEY",
    "SRF_LOG_LEVEL",
    "SRF_MAX_PREP_RETRIES",
    "SRF_MIN_AGENTS",
    "SRF_MIN_PAPERS",
    "SRF_ARXIV_DELAY_SECONDS",
    "SRF_DEBATE_CONTEXT_TOKENS",
)

_REQUIRED_OPENCLAW_VARS = (
    "SETUP_PASSWORD",
    "PORT",
    "OPENCLAW_STATE_DIR",
    "OPENCLAW_WORKSPACE_DIR",
    "OPENCLAW_GATEWAY_TOKEN",
)


def _load_ci() -> dict:
    assert _CI_PATH.exists(), f"CI workflow not found: {_CI_PATH}"
    return yaml.safe_load(_CI_PATH.read_text(encoding="utf-8"))


def _steps(ci: dict) -> list[dict]:
    jobs = ci.get("jobs", {})
    assert jobs, "No jobs defined in CI workflow"
    first_job = next(iter(jobs.values()))
    return first_job.get("steps", [])


def _step_run(step: dict) -> str:
    return step.get("run", "")


# ---------------------------------------------------------------------------
# Scenario: CI runs on push and pull_request targeting main
# ---------------------------------------------------------------------------


def test_ci_triggers_on_push_and_pull_request() -> None:
    ci = _load_ci()
    on = ci.get("on", ci.get(True, {}))  # YAML parses 'on' as True
    assert "push" in on, "CI must trigger on push"
    assert "pull_request" in on, "CI must trigger on pull_request"
    push_branches = on.get("push", {}).get("branches", [])
    pr_branches = on.get("pull_request", {}).get("branches", [])
    assert "main" in push_branches, "push trigger must target main"
    assert "main" in pr_branches, "pull_request trigger must target main"


# ---------------------------------------------------------------------------
# Scenario: CI runs ruff before pytest
# ---------------------------------------------------------------------------


def test_ci_has_ruff_step() -> None:
    steps = _steps(_load_ci())
    ruff_steps = [s for s in steps if "ruff check" in _step_run(s)]
    assert ruff_steps, "CI must have a ruff check step"
    run = _step_run(ruff_steps[0])
    assert "src/" in run
    assert "tests/" in run


def test_ci_has_pytest_step() -> None:
    steps = _steps(_load_ci())
    pytest_steps = [s for s in steps if "pytest tests/unit" in _step_run(s)]
    assert pytest_steps, "CI must have a pytest tests/unit step"


def test_ci_ruff_precedes_pytest() -> None:
    steps = _steps(_load_ci())
    runs = [_step_run(s) for s in steps]
    ruff_idx = next((i for i, r in enumerate(runs) if "ruff check" in r), None)
    pytest_idx = next((i for i, r in enumerate(runs) if "pytest tests/unit" in r), None)
    assert ruff_idx is not None, "ruff step not found"
    assert pytest_idx is not None, "pytest step not found"
    assert ruff_idx < pytest_idx, "ruff must run before pytest"


# ---------------------------------------------------------------------------
# Scenario: CI runs validate_prompts.py on pull requests
# ---------------------------------------------------------------------------


def test_ci_has_validate_prompts_step() -> None:
    steps = _steps(_load_ci())
    vp_steps = [s for s in steps if "validate_prompts.py" in _step_run(s)]
    assert vp_steps, "CI must have a validate_prompts.py step"
    step = vp_steps[0]
    assert "--dry-run" in _step_run(step)
    assert step.get("continue-on-error") is not True


# ---------------------------------------------------------------------------
# Scenario: .env.example contains all SRF Python script variables
# ---------------------------------------------------------------------------


def test_env_example_has_srf_vars() -> None:
    assert _ENV_EXAMPLE.exists(), ".env.example not found"
    text = _ENV_EXAMPLE.read_text(encoding="utf-8")
    for var in _REQUIRED_SRF_VARS:
        assert var in text, f".env.example missing: {var}"


# ---------------------------------------------------------------------------
# Scenario: .env.example contains all OpenClaw Gateway variables
# ---------------------------------------------------------------------------


def test_env_example_has_openclaw_vars() -> None:
    assert _ENV_EXAMPLE.exists(), ".env.example not found"
    text = _ENV_EXAMPLE.read_text(encoding="utf-8")
    for var in _REQUIRED_OPENCLAW_VARS:
        assert var in text, f".env.example missing: {var}"


# ---------------------------------------------------------------------------
# Scenario: no CI step uses continue-on-error: true
# ---------------------------------------------------------------------------


def test_ci_no_continue_on_error_true() -> None:
    steps = _steps(_load_ci())
    for step in steps:
        assert step.get("continue-on-error") is not True, (
            f"Step {step.get('name', '?')!r} uses continue-on-error: true"
        )
