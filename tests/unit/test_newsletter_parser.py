"""Story 3.1 — Newsletter Parser acceptance tests.

Each Gherkin scenario maps 1:1 to one test function.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures" / "newsletters"


# ---------------------------------------------------------------------------
# Scenario: parser extracts issue metadata from header
# ---------------------------------------------------------------------------


def test_parser_extracts_issue_metadata() -> None:
    from srf.newsletter.parser import parse_newsletter

    result = parse_newsletter(FIXTURES / "valid_three_papers.md")
    assert result.issue_number == 5
    assert result.subtitle == "Multi-Agent Systems Under Stress"


# ---------------------------------------------------------------------------
# Scenario: parser extracts all Primary Signal papers
# ---------------------------------------------------------------------------


def test_parser_extracts_primary_signals() -> None:
    from srf.newsletter.parser import parse_newsletter

    result = parse_newsletter(FIXTURES / "valid_three_papers.md")
    assert len(result.primary_signals) == 3
    for sig in result.primary_signals:
        assert sig.title
        assert sig.technical_summary
        assert sig.why_it_matters


# ---------------------------------------------------------------------------
# Scenario: parser normalises arxiv URL with version suffix to bare arxiv_id
# ---------------------------------------------------------------------------


def test_parser_normalises_arxiv_url_with_version_suffix() -> None:
    from srf.newsletter.parser import parse_newsletter

    result = parse_newsletter(FIXTURES / "valid_three_papers.md")
    # First paper has URL https://arxiv.org/abs/2401.12345v2
    first = result.primary_signals[0]
    assert first.arxiv_id == "2401.12345"
    assert first.source == "arxiv"


# ---------------------------------------------------------------------------
# Scenario: parser normalises arxiv URL without version suffix
# ---------------------------------------------------------------------------


def test_parser_normalises_arxiv_url_without_version_suffix() -> None:
    from srf.newsletter.parser import parse_newsletter

    result = parse_newsletter(FIXTURES / "valid_three_papers.md")
    # Second paper has URL https://arxiv.org/abs/2402.67890 (no version)
    second = result.primary_signals[1]
    assert second.arxiv_id == "2402.67890"


# ---------------------------------------------------------------------------
# Scenario: parser flags non-arxiv preprint URLs
# ---------------------------------------------------------------------------


def test_parser_flags_non_arxiv_preprint_urls() -> None:
    from srf.newsletter.parser import parse_newsletter

    result = parse_newsletter(FIXTURES / "osf_preprint.md")
    assert len(result.primary_signals) == 1
    sig = result.primary_signals[0]
    assert sig.source == "other"
    assert sig.url == "https://osf.io/preprints/psyarxiv/8hbp9_v1/"
    assert sig.arxiv_id is None


# ---------------------------------------------------------------------------
# Scenario: parser extracts Pattern Watch tension axes
# ---------------------------------------------------------------------------


def test_parser_extracts_pattern_watch() -> None:
    from srf.newsletter.parser import parse_newsletter

    result = parse_newsletter(FIXTURES / "valid_three_papers.md")
    assert isinstance(result.pattern_watch, list)
    assert len(result.pattern_watch) == 3
    for axis in result.pattern_watch:
        assert axis  # non-empty


# ---------------------------------------------------------------------------
# Scenario: parser extracts Supporting Evidence bullets
# ---------------------------------------------------------------------------


def test_parser_extracts_supporting_evidence() -> None:
    from srf.newsletter.parser import parse_newsletter

    result = parse_newsletter(FIXTURES / "valid_three_papers.md")
    assert len(result.supporting_evidence) == 5
    for item in result.supporting_evidence:
        assert item.description  # non-empty


# ---------------------------------------------------------------------------
# Scenario: parser extracts This Week's Signal narrative
# ---------------------------------------------------------------------------


def test_parser_extracts_signal_narrative() -> None:
    from srf.newsletter.parser import parse_newsletter

    result = parse_newsletter(FIXTURES / "valid_three_papers.md")
    assert result.signal_narrative
    assert len(result.signal_narrative) > 0


# ---------------------------------------------------------------------------
# Scenario: parser raises ParseError on file not found
# ---------------------------------------------------------------------------


def test_parser_raises_parse_error_on_missing_file(tmp_path: Path) -> None:
    from srf.newsletter.models import ParseError
    from srf.newsletter.parser import parse_newsletter

    missing = tmp_path / "does_not_exist.md"
    with pytest.raises(ParseError, match=re.escape(str(missing))):
        parse_newsletter(missing)


# ---------------------------------------------------------------------------
# Scenario: parser raises ParseError when no Primary Signals are found
# ---------------------------------------------------------------------------


def test_parser_raises_parse_error_when_no_primary_signals() -> None:
    from srf.newsletter.models import ParseError
    from srf.newsletter.parser import parse_newsletter

    with pytest.raises(ParseError, match="(?i)no papers"):
        parse_newsletter(FIXTURES / "no_primary_signals.md")


# ---------------------------------------------------------------------------
# Scenario: parser raises ParseError when Pattern Watch section is absent
# ---------------------------------------------------------------------------


def test_parser_raises_parse_error_when_pattern_watch_absent() -> None:
    from srf.newsletter.models import ParseError
    from srf.newsletter.parser import parse_newsletter

    with pytest.raises(ParseError, match="(?i)pattern watch"):
        parse_newsletter(FIXTURES / "missing_pattern_watch.md")
