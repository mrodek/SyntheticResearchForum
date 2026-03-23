"""Agent preparation — LLM-backed preparation for Paper Agents, Moderator, and Challenger."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import structlog

from srf.agents.models import AgentAssignment, AgentRoster, PreparationError
from srf.config import SRFConfig
from srf.extraction.models import PaperContent
from srf.llm.fallback import call_provider_directly
from srf.prompts.agents import PAPER_PREPARATION_SYSTEM, PAPER_PREPARATION_USER

logger = structlog.get_logger(__name__)

_DEFAULT_PAPER_TOKEN_BUDGET = 80000


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


@dataclass
class PreparationArtifact:
    """LLM-generated preparation result for a Paper Agent."""

    agent_id: str
    claimed_position: str
    key_arguments: list[str]
    anticipated_objections: list[str]
    epistemic_confidence: float
    status: str = "ok"

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "claimed_position": self.claimed_position,
            "key_arguments": self.key_arguments,
            "anticipated_objections": self.anticipated_objections,
            "epistemic_confidence": self.epistemic_confidence,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PreparationArtifact:
        return cls(
            agent_id=data["agent_id"],
            claimed_position=data["claimed_position"],
            key_arguments=data["key_arguments"],
            anticipated_objections=data["anticipated_objections"],
            epistemic_confidence=float(data["epistemic_confidence"]),
            status=data.get("status", "ok"),
        )


@dataclass
class ModeratorBriefing:
    """LLM-generated briefing for the Moderator agent."""

    debate_agenda: list[str]
    agent_profiles: list[dict]
    escalation_policy: str
    status: str = "ok"

    def to_dict(self) -> dict:
        return {
            "debate_agenda": self.debate_agenda,
            "agent_profiles": self.agent_profiles,
            "escalation_policy": self.escalation_policy,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ModeratorBriefing:
        return cls(
            debate_agenda=data["debate_agenda"],
            agent_profiles=data["agent_profiles"],
            escalation_policy=data["escalation_policy"],
            status=data.get("status", "ok"),
        )


@dataclass
class ChallengerPreparation:
    """LLM-generated preparation for the Challenger agent."""

    skeptical_stance: str
    challenge_angles: list[str]
    anticipated_defenses: list[str]
    status: str = "ok"

    def to_dict(self) -> dict:
        return {
            "skeptical_stance": self.skeptical_stance,
            "challenge_angles": self.challenge_angles,
            "anticipated_defenses": self.anticipated_defenses,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ChallengerPreparation:
        return cls(
            skeptical_stance=data["skeptical_stance"],
            challenge_angles=data["challenge_angles"],
            anticipated_defenses=data["anticipated_defenses"],
            status=data.get("status", "ok"),
        )


# ---------------------------------------------------------------------------
# Paper Agent preparation
# ---------------------------------------------------------------------------


async def prepare_paper_agent(
    assignment: AgentAssignment,
    paper_content: PaperContent,
    framing_question: str,
    *,
    tracker: object | None,
    config: SRFConfig,
    state: dict[str, Any],
    memory_block: str = "",
) -> PreparationArtifact:
    """Prepare a single Paper Agent via LLM call.

    Primary path: tracker.execute() — PL makes the provider call and writes
    state["last_span_id"].

    Fallback (tracker=None): call_provider_directly().

    Args:
        assignment:       Agent assignment (role, arxiv_id, agent_id).
        paper_content:    Extracted paper content.
        framing_question: Forum framing question.
        tracker:          AsyncPromptLedgerClient or None.
        config:           SRFConfig with paper_token_budget.
        state:            Mutable state dict; last_span_id written on tracker path.
        memory_block:     Memory context string (empty until Epic 2).

    Returns:
        PreparationArtifact.

    Raises:
        PreparationError: If the LLM returns malformed JSON.
    """
    budget = getattr(config, "paper_token_budget", _DEFAULT_PAPER_TOKEN_BUDGET)
    paper_text, truncated = _budget_paper_text(
        paper_content.full_text or "",
        budget,
        arxiv_id=paper_content.arxiv_id or assignment.arxiv_id or "unknown",
    )

    system_content = PAPER_PREPARATION_SYSTEM.format_map({"memory_block": memory_block})
    user_content = PAPER_PREPARATION_USER.format_map({
        "framing_question": framing_question,
        "paper_text": paper_text,
    })
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]

    if tracker is not None:
        result = await tracker.execute(
            prompt_name="agent.paper_preparation",
            messages=messages,
            mode="mode2",
            state=state,
            agent_id=assignment.agent_id,
            model={"provider": config.llm_provider, "model_name": config.llm_model},
        )
        response_text = result.response_text
        state["last_span_id"] = result.span_id
    else:
        response_text = await call_provider_directly(messages=messages, config=config)

    return _parse_preparation_artifact(response_text, assignment.agent_id)


# ---------------------------------------------------------------------------
# Moderator preparation
# ---------------------------------------------------------------------------


async def prepare_moderator(
    roster: AgentRoster,
    framing_question: str,
    paper_summaries: list[str],
    *,
    tracker: object | None,
    config: SRFConfig,
    state: dict[str, Any],
    memory_block: str = "",
) -> ModeratorBriefing:
    """Prepare the Moderator via LLM call.

    Args:
        roster:           Full AgentRoster (used to list agent profiles).
        framing_question: Forum framing question.
        paper_summaries:  Short paper summaries (not full text).
        tracker:          AsyncPromptLedgerClient or None.
        config:           SRFConfig.
        state:            Mutable state dict.
        memory_block:     Memory context string (empty until Epic 2).

    Returns:
        ModeratorBriefing.

    Raises:
        PreparationError: If the LLM returns malformed JSON.
    """
    from srf.prompts.agents import MODERATOR_BRIEFING_SYSTEM, MODERATOR_BRIEFING_USER

    paper_agents = [a for a in roster.agents if a.role == "paper_agent"]
    agent_roster_text = "\n".join(
        f"- {a.agent_id}: assigned paper {a.arxiv_id}" for a in paper_agents
    )
    summaries_text = "\n\n".join(
        f"Paper {idx + 1}: {s}" for idx, s in enumerate(paper_summaries)
    )

    system_content = MODERATOR_BRIEFING_SYSTEM.format_map({"memory_block": memory_block})
    user_content = MODERATOR_BRIEFING_USER.format_map({
        "framing_question": framing_question,
        "paper_summaries": summaries_text,
        "agent_roster": agent_roster_text,
    })
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]

    if tracker is not None:
        result = await tracker.execute(
            prompt_name="agent.moderator_briefing",
            messages=messages,
            mode="mode2",
            state=state,
            agent_id="moderator",
            model={"provider": config.llm_provider, "model_name": config.llm_model},
        )
        response_text = result.response_text
        state["last_span_id"] = result.span_id
    else:
        response_text = await call_provider_directly(messages=messages, config=config)

    return _parse_moderator_briefing(response_text)


# ---------------------------------------------------------------------------
# Challenger preparation
# ---------------------------------------------------------------------------


async def prepare_challenger(
    roster: AgentRoster,
    framing_question: str,
    paper_abstracts: list[str],
    *,
    tracker: object | None,
    config: SRFConfig,
    state: dict[str, Any],
    memory_block: str = "",
) -> ChallengerPreparation:
    """Prepare the Challenger via LLM call.

    Args:
        roster:           Full AgentRoster.
        framing_question: Forum framing question.
        paper_abstracts:  Paper abstracts (medium length — not full text).
        tracker:          AsyncPromptLedgerClient or None.
        config:           SRFConfig.
        state:            Mutable state dict.
        memory_block:     Memory context string (empty until Epic 2).

    Returns:
        ChallengerPreparation.

    Raises:
        PreparationError: If the LLM returns malformed JSON.
    """
    from srf.prompts.agents import CHALLENGER_PREPARATION_SYSTEM, CHALLENGER_PREPARATION_USER

    abstracts_text = "\n\n".join(
        f"Paper {idx + 1}: {a}" for idx, a in enumerate(paper_abstracts)
    )

    system_content = CHALLENGER_PREPARATION_SYSTEM.format_map({"memory_block": memory_block})
    user_content = CHALLENGER_PREPARATION_USER.format_map({
        "framing_question": framing_question,
        "paper_abstracts": abstracts_text,
    })
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]

    if tracker is not None:
        result = await tracker.execute(
            prompt_name="agent.challenger_preparation",
            messages=messages,
            mode="mode2",
            state=state,
            agent_id="challenger",
            model={"provider": config.llm_provider, "model_name": config.llm_model},
        )
        response_text = result.response_text
        state["last_span_id"] = result.span_id
    else:
        response_text = await call_provider_directly(messages=messages, config=config)

    return _parse_challenger_preparation(response_text)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _budget_paper_text(text: str, budget: int, arxiv_id: str) -> tuple[str, int]:
    """Truncate text to budget chars at a sentence boundary.

    Returns (truncated_text, chars_dropped). Logs WARNING when truncation occurs.
    """
    if len(text) <= budget:
        return text, 0

    # Find sentence boundary at or before budget
    cutoff = budget
    for end_char in (".", "!", "?"):
        pos = text.rfind(end_char, 0, budget)
        if pos > 0:
            cutoff = max(cutoff, pos + 1)
            break

    truncated = text[:cutoff]
    chars_dropped = len(text) - len(truncated)

    logger.warning(
        "paper text truncated",
        arxiv_id=arxiv_id,
        budget=budget,
        original_length=len(text),
        chars_dropped=chars_dropped,
    )

    return truncated, chars_dropped


def _parse_preparation_artifact(response_text: str, agent_id: str) -> PreparationArtifact:
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise PreparationError(
            f"Failed to parse preparation artifact JSON for {agent_id}: {exc}"
        ) from exc

    try:
        return PreparationArtifact(
            agent_id=data.get("agent_id", agent_id),
            claimed_position=data["claimed_position"],
            key_arguments=data["key_arguments"],
            anticipated_objections=data["anticipated_objections"],
            epistemic_confidence=float(data["epistemic_confidence"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PreparationError(
            f"parse failure: incomplete preparation artifact for {agent_id}: {exc}"
        ) from exc


def _parse_moderator_briefing(response_text: str) -> ModeratorBriefing:
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise PreparationError(f"Failed to parse moderator briefing JSON: {exc}") from exc

    try:
        return ModeratorBriefing(
            debate_agenda=data["debate_agenda"],
            agent_profiles=data["agent_profiles"],
            escalation_policy=data["escalation_policy"],
        )
    except (KeyError, TypeError) as exc:
        raise PreparationError(f"parse failure: incomplete moderator briefing: {exc}") from exc


def _parse_challenger_preparation(response_text: str) -> ChallengerPreparation:
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise PreparationError(
            f"Failed to parse challenger preparation JSON: {exc}"
        ) from exc

    try:
        return ChallengerPreparation(
            skeptical_stance=data["skeptical_stance"],
            challenge_angles=data["challenge_angles"],
            anticipated_defenses=data["anticipated_defenses"],
        )
    except (KeyError, TypeError) as exc:
        raise PreparationError(
            f"parse failure: incomplete challenger preparation: {exc}"
        ) from exc
