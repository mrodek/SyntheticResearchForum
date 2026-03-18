"""Factory helpers for building minimal NewsletterDoc / PrimarySignal test objects."""

from __future__ import annotations

from srf.newsletter.models import (
    NewsletterDoc,
    PaperCluster,
    PrimarySignal,
    SupportingEvidenceItem,
)


def make_signal(
    title: str,
    arxiv_id: str = "2401.00001",
    source: str = "arxiv",
    url: str = "https://arxiv.org/abs/2401.00001",
    technical_summary: str = "A technical summary for testing.",
    why_it_matters: str = "It matters because of reasons.",
) -> PrimarySignal:
    return PrimarySignal(
        title=title,
        url=url,
        source=source,
        arxiv_id=arxiv_id,
        technical_summary=technical_summary,
        why_it_matters=why_it_matters,
    )


def make_doc(
    tensions: list[str] | None = None,
    signals: list[PrimarySignal] | None = None,
    issue_number: int = 1,
    subtitle: str = "Test Issue",
    signal_narrative: str = "Test narrative.",
) -> NewsletterDoc:
    return NewsletterDoc(
        issue_number=issue_number,
        subtitle=subtitle,
        signal_narrative=signal_narrative,
        pattern_watch=tensions or ["tension-one", "tension-two"],
        primary_signals=signals or [make_signal("Default Paper A"), make_signal("Default Paper B")],
        supporting_evidence=[SupportingEvidenceItem(description="Evidence item.")],
    )


def make_cluster(
    tension_axis: str = "efficiency vs alignment",
    signals: list[PrimarySignal] | None = None,
    newsletter_slug: str = "test_issue",
) -> PaperCluster:
    return PaperCluster(
        tension_axis=tension_axis,
        papers=signals or [make_signal("Paper A"), make_signal("Paper B")],
        newsletter_slug=newsletter_slug,
    )
