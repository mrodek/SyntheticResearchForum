"""Story 1.6 — CI Prompt Validation Script acceptance tests."""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(details: list[dict]) -> MagicMock:
    """Build a mock httpx.Response for the register-code endpoint."""
    registered = sum(1 for d in details if d["action"] == "new")
    updated = sum(1 for d in details if d["action"] == "update")
    unchanged = sum(1 for d in details if d["action"] == "unchanged")

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "registered": registered,
        "updated": updated,
        "unchanged": unchanged,
        "dry_run": True,
        "details": details,
    }
    return mock_resp


# ---------------------------------------------------------------------------
# Scenario: script exits 0 when all prompts are in sync
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_prompts_exits_0_when_all_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.validate_prompts import run_validation

    monkeypatch.setenv("PROMPTLEDGER_API_URL", "https://pl.example.com")
    monkeypatch.setenv("PROMPTLEDGER_API_KEY", "test-key")

    details = [{"name": "srf.dummy", "action": "unchanged", "hash_changed": False}]

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=_make_response(details))

    with patch("scripts.validate_prompts.httpx.AsyncClient", return_value=mock_client):
        exit_code = await run_validation()

    assert exit_code == 0


# ---------------------------------------------------------------------------
# Scenario: script exits 1 when any prompt has an unregistered change
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_prompts_exits_1_on_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.validate_prompts import run_validation

    monkeypatch.setenv("PROMPTLEDGER_API_URL", "https://pl.example.com")
    monkeypatch.setenv("PROMPTLEDGER_API_KEY", "test-key")

    details = [{"name": "srf.changed_prompt", "action": "update", "hash_changed": True}]

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=_make_response(details))

    with patch("scripts.validate_prompts.httpx.AsyncClient", return_value=mock_client):
        exit_code = await run_validation()

    assert exit_code == 1


# ---------------------------------------------------------------------------
# Scenario: script exits 1 when a prompt is new (absent from PromptLedger)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_prompts_exits_1_on_new(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.validate_prompts import run_validation

    monkeypatch.setenv("PROMPTLEDGER_API_URL", "https://pl.example.com")
    monkeypatch.setenv("PROMPTLEDGER_API_KEY", "test-key")

    details = [{"name": "srf.new_prompt", "action": "new", "hash_changed": True}]

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=_make_response(details))

    with patch("scripts.validate_prompts.httpx.AsyncClient", return_value=mock_client):
        exit_code = await run_validation()

    assert exit_code == 1


# ---------------------------------------------------------------------------
# Scenario: script exits 0 with skip message when PROMPTLEDGER_API_URL is absent
# ---------------------------------------------------------------------------

def test_validate_prompts_skips_when_pl_not_configured(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    from scripts.validate_prompts import skip_message

    monkeypatch.delenv("PROMPTLEDGER_API_URL", raising=False)
    monkeypatch.delenv("PROMPTLEDGER_API_KEY", raising=False)

    msg = skip_message()
    assert "SKIP" in msg
    assert "PromptLedger" in msg


# ---------------------------------------------------------------------------
# Scenario: template_hash is SHA-256 of the template source
# ---------------------------------------------------------------------------

def test_checksum_returns_sha256_hex_digest() -> None:
    from scripts.validate_prompts import checksum

    template = "You are a researcher..."
    expected = hashlib.sha256(template.encode()).hexdigest()
    result = checksum(template)

    assert result == expected
    assert len(result) == 64
