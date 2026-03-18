"""Story 3.4 — Candidate Config Persistence & CLI acceptance tests (unit portion)."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.fixtures.newsletters._builders import make_cluster


def _make_config(topic: str = "test topic", slug: str = "issue_5"):
    from srf.newsletter.models import CandidateForumConfig

    return CandidateForumConfig(
        topic=topic,
        framing_question="A framing question?",
        tension_axis="tension axis",
        paper_refs=["2401.00001", "2401.00002"],
        newsletter_slug=slug,
        generated_at="2026-03-17T10:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# Scenario: save_candidate_configs writes one JSON file per config
# ---------------------------------------------------------------------------

def test_save_writes_one_file_per_config(tmp_path: Path) -> None:
    from srf.newsletter.persistence import save_candidate_configs

    configs = [_make_config("topic A"), _make_config("topic B")]
    paths = save_candidate_configs(configs, tmp_path, newsletter_slug="issue_5")

    assert len(paths) == 2
    output_dir = tmp_path / "candidates" / "issue_5"
    assert (output_dir / "candidate_1.json").exists()
    assert (output_dir / "candidate_2.json").exists()


# ---------------------------------------------------------------------------
# Scenario: saved JSON files deserialise to equivalent CandidateForumConfig
# ---------------------------------------------------------------------------

def test_saved_json_is_valid_candidate_config(tmp_path: Path) -> None:
    from srf.newsletter.persistence import save_candidate_configs

    config = _make_config()
    paths = save_candidate_configs([config], tmp_path, newsletter_slug="issue_5")

    data = json.loads(paths[0].read_text(encoding="utf-8"))
    assert data["topic"] == config.topic
    assert data["framing_question"] == config.framing_question
    assert data["paper_refs"] == config.paper_refs
    assert data["generated_at"] == config.generated_at


# ---------------------------------------------------------------------------
# Scenario: save_candidate_configs creates the output directory if absent
# ---------------------------------------------------------------------------

def test_save_creates_directory_if_absent(tmp_path: Path) -> None:
    from srf.newsletter.persistence import save_candidate_configs

    workspace = tmp_path / "new_workspace"
    assert not workspace.exists()

    save_candidate_configs([_make_config()], workspace, newsletter_slug="issue_1")

    assert (workspace / "candidates" / "issue_1").exists()


# ---------------------------------------------------------------------------
# Scenario: save_candidate_configs raises PersistenceError when root not writable
# ---------------------------------------------------------------------------

@pytest.mark.skipif(os.name == "nt", reason="chmod read-only unreliable on Windows CI")
def test_save_raises_persistence_error_on_unwritable_root(tmp_path: Path) -> None:
    from srf.newsletter.models import PersistenceError
    from srf.newsletter.persistence import save_candidate_configs

    readonly = tmp_path / "readonly"
    readonly.mkdir()
    readonly.chmod(stat.S_IREAD | stat.S_IEXEC)

    try:
        with pytest.raises(PersistenceError, match=str(readonly)):
            save_candidate_configs([_make_config()], readonly, newsletter_slug="x")
    finally:
        readonly.chmod(stat.S_IRWXU)


# ---------------------------------------------------------------------------
# Scenario: CLI script parse_newsletter.py --dry-run prints JSON without writing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cli_dry_run_prints_config_without_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.parse_newsletter import run_pipeline

    monkeypatch.setenv("SRF_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("SRF_LLM_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("SRF_LLM_API_KEY", "test-key")
    monkeypatch.delenv("PROMPTLEDGER_API_URL", raising=False)
    monkeypatch.delenv("PROMPTLEDGER_API_KEY", raising=False)

    from srf.newsletter.models import CandidateForumConfig

    fake_config = CandidateForumConfig(
        topic="test topic",
        framing_question="A question?",
        tension_axis="axis",
        paper_refs=["2401.00001"],
        newsletter_slug="test_issue",
        generated_at="2026-03-17T10:00:00+00:00",
    )

    newsletter_path = Path(__file__).parent.parent / "fixtures" / "newsletters" / "valid_three_papers.md"

    written: list = []

    with (
        patch("scripts.parse_newsletter.cluster_papers", return_value=[make_cluster()]),
        patch("scripts.parse_newsletter.generate_candidate_config", return_value=fake_config),
        patch("scripts.parse_newsletter.save_candidate_configs", side_effect=lambda *a, **kw: written.append(True) or []),
    ):
        output = await run_pipeline(
            newsletter_path=newsletter_path,
            workspace_root=tmp_path,
            dry_run=True,
            llm_client=MagicMock(),
            tracker=None,
        )

    assert not written  # dry-run: nothing persisted
    assert output  # some output produced


# ---------------------------------------------------------------------------
# Scenario: CLI skips PromptLedger when PROMPTLEDGER_API_URL is absent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cli_skips_promptledger_when_url_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.parse_newsletter import run_pipeline

    from srf.newsletter.models import CandidateForumConfig

    monkeypatch.setenv("SRF_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("SRF_LLM_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("SRF_LLM_API_KEY", "test-key")
    monkeypatch.delenv("PROMPTLEDGER_API_URL", raising=False)
    monkeypatch.delenv("PROMPTLEDGER_API_KEY", raising=False)

    fake_config = CandidateForumConfig(
        topic="t", framing_question="q?", tension_axis="a",
        paper_refs=["2401.00001"], newsletter_slug="s",
        generated_at="2026-03-17T10:00:00+00:00",
    )
    newsletter_path = Path(__file__).parent.parent / "fixtures" / "newsletters" / "valid_three_papers.md"

    with (
        patch("scripts.parse_newsletter.cluster_papers", return_value=[MagicMock()]),
        patch("scripts.parse_newsletter.generate_candidate_config", return_value=fake_config),
        patch("scripts.parse_newsletter.save_candidate_configs", return_value=[tmp_path / "c1.json"]),
    ):
        result = await run_pipeline(
            newsletter_path=newsletter_path,
            workspace_root=tmp_path,
            dry_run=False,
            llm_client=MagicMock(),
            tracker=None,  # no PromptLedger
        )

    assert result is not None
