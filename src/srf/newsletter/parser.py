"""Newsletter Markdown parser — converts raw .md files into NewsletterDoc objects."""

from __future__ import annotations

import re
from pathlib import Path

import structlog

from srf.newsletter.models import NewsletterDoc, ParseError, PrimarySignal, SupportingEvidenceItem

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_newsletter(path: Path) -> NewsletterDoc:
    """Parse a newsletter Markdown file and return a structured NewsletterDoc.

    Raises:
        ParseError: if the file is missing, or required sections are absent.
    """
    path = Path(path)
    if not path.exists():
        raise ParseError(f"Newsletter file not found: {path}")

    content = path.read_text(encoding="utf-8")
    return _parse_content(content, path)


# ---------------------------------------------------------------------------
# Internal parsing
# ---------------------------------------------------------------------------

def _parse_content(content: str, source_path: Path) -> NewsletterDoc:
    # 1 — Issue header
    issue_match = re.search(r"^## Issue #(\d+)\s*[—–-]\s*(.+)$", content, re.MULTILINE)
    if not issue_match:
        raise ParseError(f"Could not find issue header ('## Issue #N — ...') in {source_path}")
    issue_number = int(issue_match.group(1))
    subtitle = issue_match.group(2).strip()

    # 2 — Split document into H2 sections
    sections = _split_h2_sections(content)

    # 3 — Pattern Watch (required)
    pw_body = _find_section(sections, "pattern watch")
    if pw_body is None:
        raise ParseError(f"Pattern Watch section is missing from {source_path}")
    pattern_watch = _extract_bullets(pw_body)

    # 4 — Primary Signals (required; must have at least one paper)
    ps_body = _find_section(sections, "primary signals")
    primary_signals = _extract_primary_signals(ps_body or "")
    if not primary_signals:
        raise ParseError(f"No papers found in Primary Signals section of {source_path}")

    # 5 — Supporting Evidence (optional — empty list if absent)
    se_body = _find_section(sections, "supporting evidence")
    supporting_evidence = [
        SupportingEvidenceItem(description=b)
        for b in _extract_bullets(se_body or "")
    ]

    # 6 — This Week's Signal narrative (optional — empty string if absent)
    sig_body = _find_section(sections, "this week")
    signal_narrative = sig_body.strip() if sig_body else ""

    return NewsletterDoc(
        issue_number=issue_number,
        subtitle=subtitle,
        signal_narrative=signal_narrative,
        pattern_watch=pattern_watch,
        primary_signals=primary_signals,
        supporting_evidence=supporting_evidence,
    )


def _split_h2_sections(content: str) -> dict[str, str]:
    """Split content into a {heading: body} dict by '## ' headings."""
    parts = re.split(r"^## (.+)$", content, flags=re.MULTILINE)
    # parts = [pre, heading1, body1, heading2, body2, ...]
    result: dict[str, str] = {}
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        result[heading] = body
    return result


def _find_section(sections: dict[str, str], keyword: str) -> str | None:
    """Return the body of the first section whose heading contains keyword (case-insensitive).

    Skips the issue-header section (e.g. "Issue #6 — ...") so that keywords
    in the subtitle don't produce false matches.
    """
    kw = keyword.lower()
    for heading, body in sections.items():
        if re.match(r"issue\s*#\d+", heading.lower()):
            continue
        if kw in heading.lower():
            return body
    return None


def _extract_bullets(body: str) -> list[str]:
    """Extract '- item' bullet lines from a section body."""
    bullets = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            bullets.append(stripped[2:].strip())
    return bullets


def _extract_primary_signals(ps_body: str) -> list[PrimarySignal]:
    """Split the Primary Signals section body into individual PrimarySignal objects."""
    # Split on ### headings
    parts = re.split(r"^### (.+)$", ps_body, flags=re.MULTILINE)
    # parts[0] = text before first ### (usually empty preamble)
    # parts[1] = title, parts[2] = body, parts[3] = title, parts[4] = body, ...
    signals: list[PrimarySignal] = []
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        signals.append(_parse_one_signal(title, body))
    return signals


def _parse_one_signal(title: str, body: str) -> PrimarySignal:
    """Parse a single Primary Signal block into a PrimarySignal dataclass."""
    url = _extract_field(body, "URL")
    arxiv_id, source = _classify_url(url)

    if source == "other" and url:
        logger.warning(
            "non-arXiv preprint URL — flagged for manual review in Epic 4",
            url=url,
            title=title,
        )

    return PrimarySignal(
        title=title,
        url=url,
        source=source,
        arxiv_id=arxiv_id,
        technical_summary=_extract_field(body, "Technical summary"),
        why_it_matters=_extract_field(body, "Why it matters"),
    )


def _extract_field(body: str, label: str) -> str:
    """Extract content after **Label:** up to the next **Label:** marker or end."""
    marker = f"**{label}:**"
    idx = body.find(marker)
    if idx == -1:
        return ""
    after = body[idx + len(marker):].lstrip()
    # Stop at next **SomeWord: or end
    next_bold = re.search(r"\n\*\*\S", after)
    if next_bold:
        return after[: next_bold.start()].strip()
    return after.strip()


def _classify_url(url: str) -> tuple[str | None, str]:
    """Return (arxiv_id, source) for a URL.

    Normalises arxiv.org/abs/{id}[vN] to bare NNNN.NNNNN.
    Non-arXiv URLs get source='other' and arxiv_id=None.
    """
    if not url:
        return None, "unknown"

    arxiv_match = re.match(
        r"https?://arxiv\.org/abs/(\d{4}\.\d{4,5})(?:v\d+)?/?$",
        url.strip(),
    )
    if arxiv_match:
        return arxiv_match.group(1), "arxiv"

    return None, "other"
