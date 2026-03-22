# BUG-003 — Clustering Prompt Double-Brace Causes LLM Empty Response

**Status:** Fixed
**Fixed in commit:** TBD
**Reported:** 2026-03-21
**Epic context:** Epic 3 (Newsletter Parsing Pipeline), Story 3.2

---

## Symptom

During the first end-to-end Railway test run, the clustering step failed with:

```
llm returned invalid json — falling back to heuristic clustering
error='Failed to parse LLM clustering response: Expecting value: line 1 column 1 (char 0)'
```

`Expecting value: line 1 column 1 (char 0)` means `json.loads` received an empty string `""`. The LLM (Claude Haiku) returned no content.

---

## Root Cause

**PRIMARY** — `src/srf/prompts/newsletter.py`, lines 21–24

```python
Return ONLY valid JSON with this exact structure:
{{
  "axis name": ["Paper Title One", "Paper Title Two"],
  ...
}}
```

`CLUSTERING_PROMPT` uses `{{` and `}}` around the JSON example. In Python, `{{` and `}}` are escape sequences for literal `{` and `}` — but *only* when `.format()` is called on the string. `CLUSTERING_PROMPT` is never `.format()`-ted; it is passed as-is to the LLM as a system message.

The LLM therefore received `{{` and `}}` as literal characters — malformed JSON notation. This confused the model into returning empty content.

---

## Impact

- Every clustering call in production returned empty JSON
- Pipeline fell through to the heuristic fallback (added by OpenClaw agent on the volume, not committed to repo)
- No candidate configs could be generated from real LLM clustering

---

## Fix Required

Change `{{` → `{` and `}}` → `}` in the JSON example block within `CLUSTERING_PROMPT`.

---

## Risks

None. The prompt is a static string; the change only makes the JSON example syntactically correct to the LLM.

---

## TDD Plan

| # | Test | File | Phase |
|---|------|------|-------|
| 1 | `test_clustering_prompt_json_example_uses_single_braces` — asserts `{{` and `}}` are absent from `CLUSTERING_PROMPT` | `tests/unit/test_newsletter_clustering.py` | RED → GREEN |

---

## Files to Change

| File | Change |
|------|--------|
| `src/srf/prompts/newsletter.py` | `{{` → `{` and `}}` → `}` in `CLUSTERING_PROMPT` JSON example |
| `tests/unit/test_newsletter_clustering.py` | Add `test_clustering_prompt_json_example_uses_single_braces` |
