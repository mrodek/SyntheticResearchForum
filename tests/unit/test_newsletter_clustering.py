"""Story 3.2 — Paper Candidate Clustering acceptance tests."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
import structlog.testing

from tests.fixtures.newsletters._builders import make_doc, make_signal

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_execute_result(response_json: str, span_id: str = "span-cluster-001") -> MagicMock:
    result = MagicMock()
    result.response_text = response_json
    result.span_id = span_id
    return result


def _mock_tracker(response_json: str, span_id: str = "span-cluster-001") -> MagicMock:
    """Mock tracker whose execute() returns a valid ExecutionResult and writes state."""

    async def _execute(**kwargs):
        state = kwargs.get("state", {})
        state["last_span_id"] = span_id
        return _mock_execute_result(response_json, span_id)

    tracker = MagicMock()
    tracker.execute = AsyncMock(side_effect=_execute)
    return tracker


def _mock_llm(response_content: str) -> MagicMock:
    """Fallback llm_client for tracker=None tests."""
    resp = MagicMock()
    resp.content = response_content
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=resp)
    return llm


# ---------------------------------------------------------------------------
# Scenario: cluster_papers returns one PaperCluster per axis with >= 2 papers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cluster_returns_one_cluster_per_qualifying_axis() -> None:
    from srf.newsletter.clustering import cluster_papers

    doc = make_doc(
        tensions=["efficiency vs alignment", "centralised vs distributed", "formal vs empirical"],
        signals=[
            make_signal("P1"), make_signal("P2"), make_signal("P3"), make_signal("P4"),
        ],
    )
    response_json = json.dumps({
        "efficiency vs alignment": ["P1", "P2"],
        "centralised vs distributed": ["P3", "P4"],
        "formal vs empirical": ["P1"],  # only one — should be dropped
    })
    tracker = _mock_tracker(response_json)

    clusters = await cluster_papers(doc, tracker=tracker, state={"trace_id": "t1"})

    axis_names = [c.tension_axis for c in clusters]
    assert "efficiency vs alignment" in axis_names
    assert "centralised vs distributed" in axis_names
    assert "formal vs empirical" not in axis_names
    assert len(clusters) == 2


# ---------------------------------------------------------------------------
# Scenario: cluster_papers calls tracker.execute with the correct prompt name
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cluster_calls_tracker_execute_with_correct_prompt() -> None:
    from srf.newsletter.clustering import cluster_papers
    from srf.prompts.newsletter import CLUSTERING_PROMPT

    doc = make_doc(
        tensions=["axis one", "axis two"],
        signals=[make_signal("Alpha"), make_signal("Beta"), make_signal("Gamma")],
    )
    response_json = json.dumps({
        "axis one": ["Alpha", "Beta"],
        "axis two": ["Beta", "Gamma"],
    })

    captured_kwargs: list[dict] = []

    async def capturing_execute(**kwargs):
        captured_kwargs.append(kwargs)
        state = kwargs.get("state", {})
        state["last_span_id"] = "span-001"
        return _mock_execute_result(response_json)

    tracker = MagicMock()
    tracker.execute = AsyncMock(side_effect=capturing_execute)

    await cluster_papers(doc, tracker=tracker, state={"trace_id": "t1"})

    assert len(captured_kwargs) == 1
    kw = captured_kwargs[0]
    assert kw["prompt_name"] == "newsletter.paper_clustering"
    assert kw["mode"] == "mode2"

    messages = kw["messages"]
    user_msg = next(m for m in messages if m["role"] == "user")
    system_msg = next(m for m in messages if m["role"] == "system")

    assert CLUSTERING_PROMPT in system_msg["content"]
    assert "axis one" in user_msg["content"]
    assert "axis two" in user_msg["content"]
    assert "Alpha" in user_msg["content"]
    assert "Beta" in user_msg["content"]


# ---------------------------------------------------------------------------
# Scenario: cluster_papers writes last_span_id to state after tracker.execute
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cluster_writes_last_span_id_to_state() -> None:
    from srf.newsletter.clustering import cluster_papers

    doc = make_doc(tensions=["t1"], signals=[make_signal("A"), make_signal("B")])
    response_json = json.dumps({"t1": ["A", "B"]})

    state: dict = {"trace_id": "trace-001"}
    tracker = _mock_tracker(response_json, span_id="span-cluster-001")

    await cluster_papers(doc, tracker=tracker, state=state)

    assert state["last_span_id"] == "span-cluster-001"


# ---------------------------------------------------------------------------
# Scenario: cluster_papers completes without error when tracker is None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cluster_no_error_when_tracker_none() -> None:
    from srf.newsletter.clustering import cluster_papers

    doc = make_doc(tensions=["t1"], signals=[make_signal("A"), make_signal("B")])
    llm = _mock_llm(json.dumps({"t1": ["A", "B"]}))

    clusters = await cluster_papers(doc, tracker=None, state={}, llm_client=llm)
    assert isinstance(clusters, list)


# ---------------------------------------------------------------------------
# Scenario: a paper may appear in multiple clusters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cluster_paper_may_appear_in_multiple_clusters() -> None:
    from srf.newsletter.clustering import cluster_papers

    doc = make_doc(
        tensions=["efficiency vs alignment", "centralised control"],
        signals=[make_signal("A"), make_signal("B"), make_signal("C")],
    )
    response_json = json.dumps({
        "efficiency vs alignment": ["A", "B"],
        "centralised control": ["A", "C"],
    })
    tracker = _mock_tracker(response_json)

    clusters = await cluster_papers(doc, tracker=tracker, state={})
    assert len(clusters) == 2
    titles_ea = [p.title for p in clusters[0].papers]
    titles_cc = [p.title for p in clusters[1].papers]
    assert "A" in titles_ea
    assert "A" in titles_cc


# ---------------------------------------------------------------------------
# Scenario: axes with fewer than 2 papers are dropped with a warning
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cluster_drops_axes_with_fewer_than_two_papers() -> None:
    from srf.newsletter.clustering import cluster_papers

    doc = make_doc(tensions=["X", "Y"], signals=[make_signal("A"), make_signal("B")])
    response_json = json.dumps({"X": ["A"], "Y": ["A", "B"]})

    with structlog.testing.capture_logs() as logs:
        clusters = await cluster_papers(
            doc, tracker=None, state={}, llm_client=_mock_llm(response_json)
        )

    axis_names = [c.tension_axis for c in clusters]
    assert "X" not in axis_names
    assert "Y" in axis_names
    assert any(
        log.get("log_level") == "warning" and log.get("axis") == "X"
        for log in logs
    )


# ---------------------------------------------------------------------------
# Scenario: cluster_papers propagates execute() failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cluster_propagates_execute_failure() -> None:
    """A failed tracker.execute() is a hard LLM failure — it propagates, not swallows."""
    from srf.newsletter.clustering import cluster_papers

    import httpx

    doc = make_doc(tensions=["t1"], signals=[make_signal("A"), make_signal("B")])

    async def raise_503(**_kwargs):
        resp = MagicMock()
        resp.status_code = 503
        raise httpx.HTTPStatusError("503", request=MagicMock(), response=resp)

    tracker = MagicMock()
    tracker.execute = AsyncMock(side_effect=raise_503)

    with pytest.raises(httpx.HTTPStatusError):
        await cluster_papers(doc, tracker=tracker, state={"trace_id": "t1"})


# ---------------------------------------------------------------------------
# Scenario: cluster_papers raises ClusteringError on malformed LLM JSON
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cluster_raises_clustering_error_on_bad_json() -> None:
    from srf.newsletter.clustering import cluster_papers
    from srf.newsletter.models import ClusteringError

    doc = make_doc(tensions=["t1"], signals=[make_signal("A"), make_signal("B")])
    tracker = _mock_tracker("not-valid-json {{")

    with pytest.raises(ClusteringError, match="(?i)parse"):
        await cluster_papers(doc, tracker=tracker, state={})


# ---------------------------------------------------------------------------
# Scenario: cluster_papers raises ClusteringError when fewer than 2 signals exist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cluster_raises_when_fewer_than_two_signals() -> None:
    from srf.newsletter.clustering import cluster_papers
    from srf.newsletter.models import ClusteringError

    doc = make_doc(tensions=["t1"], signals=[make_signal("A")])
    tracker = MagicMock()
    tracker.execute = AsyncMock(side_effect=AssertionError("execute should not be called"))

    with pytest.raises(ClusteringError):
        await cluster_papers(doc, tracker=tracker, state={})

    tracker.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Scenario: clustering prompt is registered in the prompt registry
# ---------------------------------------------------------------------------


def test_clustering_prompt_is_registered() -> None:
    from srf.prompts.newsletter import NEWSLETTER_PROMPTS

    names = [p["name"] for p in NEWSLETTER_PROMPTS]
    assert "newsletter.paper_clustering" in names

    clustering_entry = next(p for p in NEWSLETTER_PROMPTS if p["name"] == "newsletter.paper_clustering")
    assert "{tension_axes}" in clustering_entry["template_source"]
    assert "{paper_summaries}" in clustering_entry["template_source"]
