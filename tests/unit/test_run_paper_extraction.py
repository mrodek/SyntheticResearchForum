"""Story 4.4 — run_paper_extraction.py acceptance tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


def _make_workspace_output(tmp_path: Path) -> dict:
    """Simulate the JSON output of run_workspace_setup.py."""
    workspace_path = tmp_path / "forum" / "forum-20260317-abcdef01"
    workspace_path.mkdir(parents=True)
    (workspace_path / "papers").mkdir()
    state = {
        "forum_id": "forum-20260317-abcdef01",
        "forum_status": "workspace_ready",
        "created_at": "2026-03-17T10:00:00+00:00",
        "paper_refs": ["2401.00001", "2401.00002"],
        "newsletter_slug": "issue_5",
    }
    (workspace_path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return {
        "forum_id": "forum-20260317-abcdef01",
        "workspace_path": str(workspace_path),
        "paper_refs": ["2401.00001", "2401.00002"],
        "topic": "Test Topic",
        "framing_question": "A question?",
        "trace_id": "trace-abc123",
        "forum_status": "workspace_ready",
    }


# ---------------------------------------------------------------------------
# Scenario: exits 0 and writes paper content summary to stdout JSON
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_paper_extraction_exits_0_with_papers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from srf.extraction.models import FetchResult, PaperContent
    from tests.fixtures.papers._builders import make_valid_paper_pdf

    monkeypatch.setenv("SRF_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("SRF_LLM_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("SRF_LLM_API_KEY", "test-key")
    monkeypatch.setenv("SRF_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.delenv("PROMPTLEDGER_API_URL", raising=False)
    monkeypatch.delenv("PROMPTLEDGER_API_KEY", raising=False)

    stdin_data = _make_workspace_output(tmp_path)
    workspace_path = Path(stdin_data["workspace_path"])

    pdf1 = workspace_path / "papers" / "2401.00001.pdf"
    pdf2 = workspace_path / "papers" / "2401.00002.pdf"
    make_valid_paper_pdf(pdf1)
    make_valid_paper_pdf(pdf2)

    mock_fetch_results = [
        FetchResult(arxiv_id="2401.00001", status="ok", pdf_path=pdf1),
        FetchResult(arxiv_id="2401.00002", status="ok", pdf_path=pdf2),
    ]
    mock_paper_contents = [
        PaperContent(
            arxiv_id="2401.00001", pdf_path=pdf1,
            full_text="full text 1", abstract="abstract 1",
            page_count=1, extraction_status="ok",
        ),
        PaperContent(
            arxiv_id="2401.00002", pdf_path=pdf2,
            full_text="full text 2", abstract="abstract 2",
            page_count=1, extraction_status="ok",
        ),
    ]

    with (
        patch("scripts.run_paper_extraction.fetch_papers_for_forum", new=AsyncMock(return_value=mock_fetch_results)),
        patch("scripts.run_paper_extraction.extract_papers_for_forum", return_value=mock_paper_contents),
    ):
        from scripts.run_paper_extraction import _run as extraction_run
        output = await extraction_run(stdin_data)

    assert "papers" in output
    assert len(output["papers"]) == 2
    assert output["forum_status"] == "extraction_complete"


# ---------------------------------------------------------------------------
# Scenario: exits 1 when fewer than SRF_MIN_PAPERS are successfully extracted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_paper_extraction_raises_when_too_few_papers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from srf.extraction.models import ExtractionError

    monkeypatch.setenv("SRF_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("SRF_LLM_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("SRF_LLM_API_KEY", "test-key")
    monkeypatch.setenv("SRF_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.delenv("PROMPTLEDGER_API_URL", raising=False)
    monkeypatch.delenv("PROMPTLEDGER_API_KEY", raising=False)

    stdin_data = _make_workspace_output(tmp_path)

    with (
        patch("scripts.run_paper_extraction.fetch_papers_for_forum", new=AsyncMock(return_value=[])),
        patch(
            "scripts.run_paper_extraction.extract_papers_for_forum",
            side_effect=ExtractionError("insufficient papers extracted: 0 succeeded"),
        ),
    ):
        from scripts.run_paper_extraction import _run as extraction_run
        with pytest.raises(ExtractionError):
            await extraction_run(stdin_data)


# ---------------------------------------------------------------------------
# Scenario: srf_forum.yaml contains workspace_setup and paper_extraction steps
# ---------------------------------------------------------------------------


def test_srf_forum_yaml_has_correct_steps() -> None:
    import yaml

    yaml_path = Path("workflows/srf_forum.lobster")
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

    step_ids = [s["id"] for s in data["steps"]]
    assert "workspace_setup" in step_ids
    assert "paper_extraction" in step_ids
    assert step_ids.index("workspace_setup") < step_ids.index("paper_extraction")

    ws_step = next(s for s in data["steps"] if s["id"] == "workspace_setup")
    pe_step = next(s for s in data["steps"] if s["id"] == "paper_extraction")

    assert "run_workspace_setup.py" in ws_step["command"]
    assert "LOBSTER_ARGS_JSON" in ws_step["command"]
    assert "run_paper_extraction.py" in pe_step["command"]
    assert "/data/venv/bin/python" in pe_step["command"]
    assert pe_step["stdin"] == "$workspace_setup.json"


# ---------------------------------------------------------------------------
# Scenario: run_paper_extraction.py writes updated state.json checkpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_paper_extraction_updates_state_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from srf.extraction.models import PaperContent

    monkeypatch.setenv("SRF_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("SRF_LLM_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("SRF_LLM_API_KEY", "test-key")
    monkeypatch.setenv("SRF_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.delenv("PROMPTLEDGER_API_URL", raising=False)
    monkeypatch.delenv("PROMPTLEDGER_API_KEY", raising=False)

    stdin_data = _make_workspace_output(tmp_path)
    workspace_path = Path(stdin_data["workspace_path"])

    mock_contents = [
        PaperContent(
            arxiv_id="2401.00001", pdf_path=None,
            full_text="text", abstract="abs",
            page_count=1, extraction_status="ok",
        ),
        PaperContent(
            arxiv_id="2401.00002", pdf_path=None,
            full_text="text", abstract="abs",
            page_count=1, extraction_status="ok",
        ),
    ]

    with (
        patch("scripts.run_paper_extraction.fetch_papers_for_forum", new=AsyncMock(return_value=[])),
        patch("scripts.run_paper_extraction.extract_papers_for_forum", return_value=mock_contents),
    ):
        from scripts.run_paper_extraction import _run as extraction_run
        await extraction_run(stdin_data)

    state = json.loads((workspace_path / "state.json").read_text())
    assert state["forum_status"] == "extraction_complete"
    assert state["extracted_paper_count"] == 2
