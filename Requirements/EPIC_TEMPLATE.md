# ResearchKG — Epic & Story Writing Standards

This document is the canonical template and rule set for writing epics, stories, bug
documents, and tech debt entries in this project. Follow it exactly — consistency makes
epics machine-readable by Claude Code and human-reviewable at a glance.

---

## Table of Contents

1. [Epic Structure](#epic-structure)
2. [Story Structure](#story-structure)
3. [Acceptance Criteria — Gherkin Format](#acceptance-criteria--gherkin-format)
4. [Bug Documents](#bug-documents)
5. [Tech Debt Tracker](#tech-debt-tracker)
6. [Naming & File Conventions](#naming--file-conventions)
7. [Quick Reference Checklist](#quick-reference-checklist)

---

## Epic Structure

**Filename:** `requirements/srf_epic_{NN}_{slug}.md`
**Title line:** `# Epic {N}: {Title} — {Subtitle}`

Every epic must contain the following sections in order:

```
# Epic {N}: {Title} — {Subtitle}

## Prerequisites
## Context
## What We Gain
## Architecture Decisions   ← omit if none
## Stories
## Implementation Order
## Verification Checklist
## Critical Files
```

### Prerequisites

List any epics or stories that must be complete before this epic begins. If none, write
`None — this epic is self-contained.`

### Context

2–4 sentences explaining *why* this epic exists. What user problem or system gap does it
address? Do not describe the solution here — that belongs in the stories.

### What We Gain

A before/after table. Be concrete.

```markdown
| Gap (before) | After this epic |
|---|---|
| Specific problem A | Specific outcome A |
| Specific problem B | Specific outcome B |
```

### Architecture Decisions

Any non-obvious technical choices and the reasoning behind them. Include alternatives
considered and why they were rejected. Omit this section entirely if there are no
meaningful decisions to document.

### Stories

See [Story Structure](#story-structure) below. Number stories `{epic}.{story}` (e.g. 24.1,
24.2). Stories should be independently deployable slices of value where possible.

### Implementation Order

A dependency graph in text form:

```
Story N.1 → Story N.2 → Story N.3
Story N.4 (parallel with N.2)
```

State explicitly which stories can run in parallel.

### Verification Checklist

Shell commands that confirm each story is working:

```bash
# After N.1
pytest tests/unit/test_foo.py -v

# After N.2
python scripts/some_script.py --dry-run
```

### Critical Files

A flat list of files NEW'd or MODIFIED by this epic.

---

## Story Structure

Each story lives inside its parent epic file under the `## Stories` section.

```markdown
### Story {N.M} — {Title}

**As a** {role},
**I would like** {capability or behaviour},
**so that** {benefit or outcome}.

**Context** _(optional — 1–2 sentences of background, skip if self-evident)_

**Files:**
- NEW: `path/to/new_file.py`
- MODIFY: `path/to/existing_file.py`
- MODIFY: `tests/unit/test_existing.py`

**Acceptance Criteria:**

```gherkin
Scenario: {descriptive scenario title}
  Given {initial context or system state}
  When  {action or event}
  Then  {expected outcome}

Scenario: {another scenario}
  Given ...
  When  ...
  Then  ...
```

**TDD Notes** _(optional — flag tricky test setup, mocking approach, or test order)_
```

### Role vocabulary

Use consistent roles across all stories:

| Role | Meaning |
|---|---|
| `researcher` | End user querying the graph via Claude Desktop |
| `system` | Automated pipeline (scanner, cron job) |
| `developer` | Engineer maintaining or extending ResearchKG |
| `MCP server` | The server process handling a tool call |

### Slicing rules

- One story = one independently mergeable unit of work
- A story that requires >5 files modified is probably two stories
- A story with >8 Gherkin scenarios is probably two stories
- Infrastructure stories (schema, config) should precede feature stories that depend on them

---

## Acceptance Criteria — Gherkin Format

Acceptance criteria are written as Gherkin scenarios. Every scenario becomes one pytest
test function. The scenario title maps directly to the test name.

### Format rules

```gherkin
Scenario: {short imperative description — this becomes the test function name}
  Given {the system state before the action — what is set up or assumed}
  When  {the specific action taken — one action per scenario}
  Then  {the observable outcome — what can be asserted}
  And   {additional assertion — use sparingly}
```

- **One action per scenario** (`When` clause). If you need two actions, write two scenarios.
- **`Then` must be assertable in code** — not "the user feels satisfied" but "the response
  dict contains `success: True`".
- **Avoid UI/narrative language** — "the system should…" → "the function returns…"
- **Negative scenarios are mandatory** for any feature with error paths. Always include at
  least one scenario for the unhappy path.

### Gherkin → pytest mapping

```gherkin
Scenario: log_span returns None when no trace is active
  Given no call to start_trace() has been made in this context
  When  log_anthropic_call() is called
  Then  it returns None without raising an exception
```

becomes:

```python
@pytest.mark.asyncio
async def test_log_span_returns_none_when_no_trace_active():
    # Given: no start_trace() call — ContextVar default is None
    tracker = ExecutionTracker(client=mock_client, fail_silently=True)
    # When
    result = await tracker.log_anthropic_call(
        prompt_key="extraction.paper", input_text="x",
        output_text="y", model="claude-haiku-4-5-20251001",
        usage=mock_usage, duration_ms=100,
    )
    # Then
    assert result is None
```

### Background (shared Given)

If multiple scenarios share the same setup, use `Background`:

```gherkin
Background:
  Given a PromptLedgerClient configured with base_url "http://localhost:8100"
  And   the API returns 200 on /health

Scenario: register_code_prompts succeeds with valid payload
  When  register_code_prompts() is called with 3 prompts
  Then  it returns a result with registered count of 3
```

---

## Bug Documents

**Filename:** `requirements/bugs/BUG-{NN}-{short-slug}.md`
_(Use sequential two-digit numbers: BUG-01, BUG-02, …)_

**Title line:** `# BUG-{NN}: {One-sentence description of the symptom}`

### Required sections

```
# BUG-{NN}: {Symptom description}

**Status:** Open | In Progress | Fixed
**Severity:** Critical | High | Medium | Low
**Discovered:** YYYY-MM-DD
**Affected Component:** {module path + function name}
**Fixed in commit:** {sha} ← add when resolved

---

## Symptom
## Root Cause
## Impact
## Fix Required
## Risks
## TDD Plan
## Files to Change
```

### Severity guide

| Severity | Meaning |
|---|---|
| Critical | Data loss, security issue, or system completely broken |
| High | Core feature produces wrong output silently |
| Medium | Feature degraded but workaround exists |
| Low | Minor inconsistency or cosmetic issue |

### Symptom

Describe what the user observes. Include concrete examples — specific paper IDs, log
lines, return values. Do not explain causes here.

### Root Cause

Label each cause PRIMARY, SECONDARY, or CONTRIBUTING. Include:
- **File** and **function/line** where the fault lives
- A code snippet showing the broken code
- An explanation of *why* it produces the symptom

If there are multiple root causes, number them (Root Cause 1, Root Cause 2…).

### Impact

A table:

```markdown
| What breaks | Effect |
|---|---|
| Feature X | Specific bad outcome |
```

### Fix Required

Describe the fix at the code level. Include:
- The corrected code snippet (or pseudocode if full code isn't known yet)
- Why this fix addresses the root cause
- Any migration or backfill needed for existing data

### Risks

Any ways the fix could introduce regressions. Be specific:
- Tests that will intentionally go RED (not regressions — they need rewriting)
- Data type mismatches
- Race conditions introduced or removed

### TDD Plan

```
1. Write failing test: {describe what the test asserts}
2. Confirm RED
3. Implement fix
4. Confirm GREEN
5. Run full suite — confirm no regressions
```

### Files to Change

A table matching the epic format:

```markdown
| File | Change |
|---|---|
| `src/module/file.py` | Fix root cause |
| `tests/unit/test_file.py` | Add regression tests |
```

---

## Tech Debt Tracker

**File:** `requirements/tech_debt_tracker.md`

Add new entries at the **bottom** of the file (oldest first — debt accumulates forward).

### Entry format

```markdown
## [TD-{NNN}] {Short title — what the limitation is}

**File:** `src/path/to/file.py`
**Introduced:** {Story or Epic that created this debt}
**Risk:** Critical | High | Medium | Low

### Description
What the limitation is and why it was accepted at the time. Include the original
rationale if it was a deliberate trade-off (e.g. "deferred to keep Epic 11 scope small").

### Impact
- Bullet list of what breaks or degrades when this debt bites
- Be specific: which queries, which tools, which user-facing behaviours

### Trigger
The specific event or condition that would turn this from latent risk into active problem.
Example: "Adding a non-AI/ML ingestion source."

### Suggested Fix
- Actionable steps to resolve when the trigger arrives
- Include file names, function names, and any schema changes needed
- If the fix is an epic, reference it: "Addressed by Epic 24 Story 24.1"
```

### When to add a tech debt entry

Add an entry when you:
- Make a deliberate simplification that you know will need revisiting
- Hardcode a value that should eventually be configurable
- Leave an edge case unhandled because it's not worth fixing now
- Write a comment like `# TODO` or `# FIXME` in the code

Do **not** add entries for:
- Bugs (use a bug document instead)
- Future features (use an epic instead)
- Style preferences

---

## Naming & File Conventions

| Artefact | Location | Filename pattern |
|---|---|---|
| Epic | `requirements/` | `kg_epic_{NN}_{slug}.md` |
| Bug document | `requirements/bugs/` | `BUG-{NN}-{slug}.md` |
| Tech debt | `requirements/tech_debt_tracker.md` | single file, append entries |
| Cross-project spec | `requirements/` | `{project}_{epic or doc type}.md` |

**Numbering:**
- Epic numbers are sequential across the project. Check existing files for the next N.
- Bug numbers are sequential across the project. Check `requirements/bugs/` for next NN.
- Tech debt IDs are sequential. Check `tech_debt_tracker.md` for next NNN.

**Slugs** use lowercase underscores. Keep them short (2–4 words). Examples:
- `kg_epic_24_concept_ontology.md`
- `BUG-05-arxiv-rate-limit.md`

---

## Quick Reference Checklist

### Before writing an epic

- [ ] Checked that prerequisite epics are identified
- [ ] Read the relevant existing code before describing the solution
- [ ] Confirmed epic number is the next unused integer

### For each story

- [ ] User story written: "As a… I would like… so that…"
- [ ] Role is from the standard vocabulary
- [ ] Every acceptance criterion is a Gherkin scenario
- [ ] At least one negative/unhappy-path scenario exists
- [ ] Files list distinguishes NEW from MODIFY
- [ ] TDD: tests are listed before implementation is described

### For a bug document

- [ ] Symptom section describes observable behaviour only (no causes)
- [ ] Each root cause has a file + line + code snippet
- [ ] TDD plan lists test → RED → implement → GREEN order
- [ ] Severity is set correctly (silent data corruption = High or Critical)
- [ ] `**Fixed in commit:**` line updated after fix is merged

### For tech debt

- [ ] Added to bottom of `tech_debt_tracker.md` (not top)
- [ ] Trigger condition is specific (not "someday")
- [ ] Suggested fix names actual files and functions
