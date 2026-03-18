"""Paper candidate clustering — semantic mapping of papers to tension axes via LLM."""

from __future__ import annotations

import json
from typing import Any

import structlog

from srf.newsletter.models import ClusteringError, NewsletterDoc, PaperCluster, PrimarySignal
from srf.prompts.newsletter import CLUSTERING_PROMPT

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def cluster_papers(
    doc: NewsletterDoc,
    *,
    tracker: object | None,
    state: dict[str, Any],
    llm_client: Any | None = None,
) -> list[PaperCluster]:
    """Semantically assign Primary Signal papers to Pattern Watch tension axes.

    Primary path: tracker.execute() — PL makes the provider call and auto-creates
    the span, writing state["last_span_id"].

    Fallback (tracker=None): llm_client.complete() — used in local dev and unit
    tests. Replaced by call_provider_directly() in Epic 5 Story 5.1.

    Raises:
        ClusteringError: if fewer than 2 Primary Signals exist, or if the LLM
                         returns malformed JSON.
        RuntimeError: if both tracker and llm_client are None.
    """
    if len(doc.primary_signals) < 2:
        raise ClusteringError(
            f"Cannot cluster: need at least 2 Primary Signals, got {len(doc.primary_signals)}"
        )

    messages = _build_messages(doc)
    response_text = await _call_llm(messages, tracker=tracker, state=state, llm_client=llm_client)
    axis_map = _parse_llm_response(response_text)
    return _build_clusters(axis_map, doc)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _call_llm(
    messages: list[dict[str, str]],
    *,
    tracker: object | None,
    state: dict[str, Any],
    llm_client: Any | None,
) -> str:
    if tracker is not None:
        result = await tracker.execute(
            prompt_name="newsletter.paper_clustering",
            messages=messages,
            mode="mode2",
            state=state,
        )
        return result.response_text
    if llm_client is not None:
        response = await llm_client.complete(messages)
        return response.content
    raise RuntimeError(
        "cluster_papers requires either tracker or llm_client; both are None"
    )


def _build_messages(doc: NewsletterDoc) -> list[dict[str, str]]:
    tension_axes = "\n".join(f"- {t}" for t in doc.pattern_watch)
    paper_summaries = "\n\n".join(
        f"Title: {s.title}\nSummary: {s.technical_summary}"
        for s in doc.primary_signals
    )
    user_content = (
        f"Tension axes:\n{tension_axes}\n\nPapers:\n{paper_summaries}"
    )
    return [
        {"role": "system", "content": CLUSTERING_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _parse_llm_response(content: str) -> dict[str, list[str]]:
    """Parse the LLM's JSON response into an axis → [title] mapping."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ClusteringError(f"Failed to parse LLM clustering response: {exc}") from exc
    if not isinstance(data, dict):
        raise ClusteringError("LLM clustering response is not a JSON object")
    return data


def _build_clusters(
    axis_map: dict[str, list[str]],
    doc: NewsletterDoc,
) -> list[PaperCluster]:
    """Convert an axis → titles mapping into PaperCluster objects.

    Drops any axis that ends up with fewer than 2 papers after resolving titles.
    """
    title_to_signal: dict[str, PrimarySignal] = {s.title: s for s in doc.primary_signals}

    clusters: list[PaperCluster] = []
    for axis, titles in axis_map.items():
        matched = [title_to_signal[t] for t in titles if t in title_to_signal]
        if len(matched) < 2:
            logger.warning(
                "axis dropped — insufficient papers",
                axis=axis,
                matched_count=len(matched),
            )
            continue
        clusters.append(PaperCluster(tension_axis=axis, papers=matched))

    return clusters
