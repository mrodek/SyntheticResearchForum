"""Newsletter domain models."""

from __future__ import annotations

from dataclasses import dataclass, field


class ParseError(ValueError):
    """Raised when a newsletter file cannot be parsed."""


class ClusteringError(ValueError):
    """Raised when paper clustering fails."""


class ConfigGenerationError(ValueError):
    """Raised when candidate config generation fails."""


class PersistenceError(OSError):
    """Raised when candidate configs cannot be persisted to disk."""


class ToolError(RuntimeError):
    """Raised when an MCP tool operation fails."""


@dataclass
class PrimarySignal:
    title: str
    url: str
    source: str  # "arxiv" | "other"
    arxiv_id: str | None
    technical_summary: str
    why_it_matters: str


@dataclass
class SupportingEvidenceItem:
    description: str


@dataclass
class NewsletterDoc:
    issue_number: int
    subtitle: str
    signal_narrative: str
    pattern_watch: list[str]
    primary_signals: list[PrimarySignal]
    supporting_evidence: list[SupportingEvidenceItem]


@dataclass
class PaperCluster:
    tension_axis: str
    papers: list[PrimarySignal]
    newsletter_slug: str = ""


@dataclass
class CandidateForumConfig:
    topic: str
    framing_question: str
    tension_axis: str
    paper_refs: list[str]  # arxiv_ids (or urls for non-arxiv)
    newsletter_slug: str
    generated_at: str
    source_papers: list[PrimarySignal] = field(default_factory=list)
