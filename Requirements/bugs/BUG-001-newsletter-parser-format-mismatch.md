# BUG-001 — Newsletter Parser Format Mismatch

**Reported:** 2026-03-20
**Fixed in commit:** _(pending)_

---

## Symptom

Running `parse_newsletter.py` against `.newsletters/weekly_field_notes_issue_1.md` raises:

```
ParseError: Could not find issue header ('## Issue #N — ...') in weekly_field_notes_issue_1.md
```

Even when the issue header is present in the file, the parser exits immediately because it expects a Markdown H2 heading but the actual newsletter uses bold inline text. Two additional failures occur downstream once the header mismatch is corrected:

1. URL extraction returns empty string for all papers — no URL is recorded.
2. Pattern Watch produces an empty list — ParseError would fire if the Pattern Watch section were absent, but instead it silently drops all watch items.

---

## Root Cause

### PRIMARY — Issue header regex only matches H2 heading format

**File:** `src/srf/newsletter/parser.py` line 38

```python
issue_match = re.search(r"^## Issue #(\d+)\s*[—–-]\s*(.+)$", content, re.MULTILINE)
```

The fixture format used during development has `## Issue #5 — ...` (H2 heading). The actual newsletter format uses `**Issue #1 — ...**` (bold inline text, no H2 prefix). The regex never matches; the function raises ParseError before any other processing occurs.

### SECONDARY — URL field extraction uses `**URL:**` label, not `[Link](URL)` markdown link

**File:** `src/srf/newsletter/parser.py` line 133

```python
url = _extract_field(body, "URL")
```

`_extract_field` looks for `**URL:** https://...` in the signal body. The actual newsletter uses:

```
**arXiv:2602.16662** | [Link](https://arxiv.org/abs/2602.16662v1)
```

No `**URL:**` label is present. The extracted `url` is always `""`, so every paper is classified as `source="unknown"` and `arxiv_id=None`.

### CONTRIBUTING — Pattern Watch extraction requires bullet points; actual format uses paragraphs

**File:** `src/srf/newsletter/parser.py` line 51

```python
pattern_watch = _extract_bullets(pw_body)
```

`_extract_bullets` collects lines starting with `- `. The actual newsletter Pattern Watch section contains bold-headed prose paragraphs:

```
**Retrieval as a replacement for stateful pipelines.** Two papers this week...

**Collective and population-level effects becoming first-class.** Three papers...
```

No bullet lines exist; `_extract_bullets` returns `[]`. The `NewsletterDoc` is constructed with an empty `pattern_watch` list — silently losing all watch items. The downstream config generator relies on these strings.

---

## Impact

- `parse_newsletter.py` cannot process any actual newsletter file. The entire pipeline is blocked from Phase 1.
- No papers are extracted, so no forum config can be generated.
- Integration testing of Phases 5–12 cannot proceed until this is fixed.

---

## Fix Required

1. **Issue header:** Accept both `## Issue #N — ...` (H2) and `**Issue #N — ...**` (bold inline). Try H2 regex first; fall back to bold regex.

2. **URL extraction:** If `**URL:**` field not found, attempt `re.search(r"\[Link\]\((.+?)\)", body)` to extract URL from markdown link syntax.

3. **Pattern Watch:** If `_extract_bullets` returns empty, fall back to extracting non-empty paragraphs from the section body (split on blank lines, strip each, discard empties).

---

## Risks

- The H2 header fallback must not match arbitrary `**bold**` text in section bodies — constrain the regex to line-start anchor.
- The paragraph fallback for Pattern Watch may include section separator lines (`---`) — filter those out.
- No changes to existing fixture files; all existing tests must remain GREEN.

---

## TDD Plan

1. Add fixture `tests/fixtures/newsletters/actual_format.md` using the bold-header / `[Link](URL)` / paragraph-watch format.
2. Write three failing tests (RED):
   - `test_parser_handles_bold_issue_header`
   - `test_parser_extracts_url_from_markdown_link`
   - `test_parser_extracts_pattern_watch_paragraphs`
3. Fix `src/srf/newsletter/parser.py` — three targeted changes.
4. Confirm all tests GREEN (new + existing).

---

## Files to Change

| File | Change |
|------|--------|
| `tests/fixtures/newsletters/actual_format.md` | NEW: fixture with actual newsletter format |
| `tests/unit/test_newsletter_parser.py` | ADD: three new test functions |
| `src/srf/newsletter/parser.py` | MODIFY: `_parse_content`, `_parse_one_signal`, `_extract_paragraphs` (new helper) |
