# BUG-005 — srf_forum.yaml: wrong file extension and invalid approval syntax

**Status:** Fixed
**Fixed in commit:** 2026-03-23 — see progress_tracker.md

---

## Symptom

Invoking the Lobster workflow via the skill results in the pipeline failing to load. The Lobster
CLI/plugin expects `.lobster` files; `srf_forum.yaml` is not a recognised workflow file.
Additionally, the `editorial_review_gate` approval step uses `approval: required` which is not
valid Lobster syntax — the value must be a human-readable prompt string.

---

## Root Cause

**PRIMARY — Wrong file extension**

File: `workflows/srf_forum.yaml`

The Lobster README explicitly states:

```
lobster run path/to/workflow.lobster
lobster run --file path/to/workflow.lobster --args-json '{...}'
```

Lobster workflow files use the `.lobster` extension. The YAML content format inside the file is
correct, but the filename `srf_forum.yaml` is not recognised as a Lobster workflow file.

**SECONDARY — Invalid `approval:` field value**

File: `workflows/srf_forum.yaml` (the `editorial_review_gate` step)

```yaml
- id: editorial_review_gate
  approval: required    # ← BUG: must be a human-readable prompt string
```

The Lobster README shows the `approval:` value is a human-readable message displayed at the
approval gate, e.g.:

```yaml
approval: Want jacket advice from the LLM?
```

The value `required` is not a valid prompt string.

**CONTRIBUTING — Skill pipeline path uses wrong extension**

File: `skills/review_forum_debate_format/SKILL.md`

```
{"action": "run", "pipeline": "/data/srf/workflows/srf_forum.yaml", ...}
```

Must reference the `.lobster` file.

---

## Impact

- Pipeline cannot be loaded by Lobster — workflow file is not found or not recognised.
- Even if found, the approval gate would fail due to invalid `approval:` value.

---

## Fix Required

1. **Rename** `workflows/srf_forum.yaml` → `workflows/srf_forum.lobster`
2. **Fix** `editorial_review_gate` step: `approval: required` → `approval: "Approve forum results for publication?"`
3. **Update** `skills/review_forum_debate_format/SKILL.md` pipeline path to `/data/srf/workflows/srf_forum.lobster`
4. **Update** all tests that open `workflows/srf_forum.yaml` to open `workflows/srf_forum.lobster`

---

## TDD Plan

```python
# In tests/unit/test_run_debate_bridge.py

def test_srf_forum_workflow_file_has_lobster_extension():
    # workflows/srf_forum.lobster must exist
    # workflows/srf_forum.yaml must NOT exist

def test_srf_forum_approval_step_has_string_message():
    # editorial_review_gate approval value must be a non-empty string
    # (not the literal word "required")

def test_review_forum_skill_references_lobster_file():
    # SKILL.md must reference srf_forum.lobster, not srf_forum.yaml
```

---

## Files to Change

- RENAME: `workflows/srf_forum.yaml` → `workflows/srf_forum.lobster`
- MODIFY: `skills/review_forum_debate_format/SKILL.md`
- MODIFY: `tests/unit/test_run_debate_bridge.py`
- MODIFY: `tests/unit/test_run_paper_extraction.py`
- MODIFY: `tests/unit/test_run_preparation.py`
