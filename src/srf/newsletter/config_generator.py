"""Forum Config Generation — produces CandidateForumConfig from a PaperCluster."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from srf.newsletter.models import (
    CandidateForumConfig,
    ConfigGenerationError,
    PaperCluster,
)
from srf.prompts.newsletter import FRAMING_QUESTION_PROMPT

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate_candidate_config(
    cluster: PaperCluster,
    *,
    tracker: object | None,
    state: dict[str, Any],
    llm_client: Any | None = None,
) -> CandidateForumConfig:
    """Generate a CandidateForumConfig from a PaperCluster.

    Primary path: tracker.execute() — PL makes the provider call and auto-creates
    the span, writing state["last_span_id"].

    Fallback (tracker=None): llm_client.complete() — used in local dev and unit
    tests. Replaced by call_provider_directly() in Epic 5 Story 5.1.

    Raises:
        ConfigGenerationError: if the LLM returns an empty framing question.
        RuntimeError: if both tracker and llm_client are None.
    """
    messages = _build_messages(cluster)
    framing_question = await _call_llm(
        messages, tracker=tracker, state=state, llm_client=llm_client
    )
    framing_question = framing_question.strip()

    if not framing_question:
        raise ConfigGenerationError(
            "LLM returned an empty framing question for cluster: "
            f"'{cluster.tension_axis}'"
        )

    paper_refs = [
        p.arxiv_id if p.arxiv_id else p.url
        for p in cluster.papers
    ]

    return CandidateForumConfig(
        topic=cluster.tension_axis,
        framing_question=framing_question,
        tension_axis=cluster.tension_axis,
        paper_refs=paper_refs,
        newsletter_slug=cluster.newsletter_slug,
        generated_at=datetime.now(UTC).isoformat(),
        source_papers=cluster.papers,
    )


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
            prompt_name="newsletter.framing_question",
            messages=messages,
            mode="mode2",
            state=state,
        )
        return result.response_text
    if llm_client is not None:
        response = await llm_client.complete(messages)
        return response.content
    raise RuntimeError(
        "generate_candidate_config requires either tracker or llm_client; both are None"
    )


def _build_messages(cluster: PaperCluster) -> list[dict[str, str]]:
    paper_titles = "\n".join(f"- {p.title}" for p in cluster.papers)
    user_content = (
        f"Tension: {cluster.tension_axis}\n\nPapers:\n{paper_titles}"
    )
    return [
        {"role": "system", "content": FRAMING_QUESTION_PROMPT},
        {"role": "user", "content": user_content},
    ]
