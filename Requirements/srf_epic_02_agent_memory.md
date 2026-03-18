# Epic 2: Agent Memory — Role-Scoped Behavioral Memory with Editorial Governance

## Prerequisites

- **Epic 1** (Stories 1.1–1.6) — project scaffold, config, logging, PromptLedger observability, and span utilities must exist.
- **Epic 5** (Agent Preparation Phase) — agent system prompt structures and preparation context patterns must be defined before the memory injection format (Story 2.4) can be finalised. You cannot write a well-formed memory block without knowing what you are injecting it into.
- **Epic 6** (Debate Engine) — the behavioral signals worth storing only become observable once real agents have debated. Schemas written before this exist are speculative; schemas written after are grounded in real agent behavior.
- **Epic 7** (Synthesis & Evaluation) — the evaluation artifact format, scoring dimensions, and behavioral flags are produced by this epic. Story 2.2 (candidate extraction) takes the `evaluation_block` as its primary input. This contract must be fixed before candidate extraction can be implemented.

This epic is therefore sequenced **after the first complete forum run** (Epics 1–8). The system runs correctly without memory — all injection points gracefully return empty blocks when no approved snapshot exists. Memory makes debates better from run two onward; it is not required for run one.

---

## Context

SRF runs weekly. Without cross-debate memory, agents repeat known failure modes, miss recurring tension structures, and produce inconsistent evaluation scores with no calibration mechanism. However, unbounded or autonomous memory creates emergent personality drift, breaks reproducibility, and makes governance impossible.

This epic implements the governed behavioral memory system defined in §10 of the architecture spec: a role-scoped memory store with an editorial approval gate on every write, a token-budgeted injection at the Preparation Phase, and full version-stamping so that any forum run remains reproducible.

**Why this epic is sequenced after the first complete run:**
Memory is a consumer of signals produced by the debate engine and evaluation pipeline. Building it before those signals exist means writing schemas against invented examples, extraction rules against a fabricated artifact format, and injection logic against unwritten agent prompts. Each of those decisions would need revisiting once the real upstream systems exist. Sequencing Epic 2 after Epics 1–8 means all interface contracts are fixed before a line of memory code is written — schemas reflect real behavioral signals, extraction rules are tested against real evaluation artifacts, and injection format is validated against real agent system prompts.

---

## What We Gain

| Gap (before) | After this epic |
|---|---|
| Agents repeat known weak arguments every forum | Preparation context includes approved behavioral signals from prior debates |
| No mechanism to track recurring tensions across forums | Synthesis Agent memory accumulates `unresolved_question_clusters` and `tension_taxonomy` |
| Evaluation scores drift with no calibration signal | Evaluator memory stores score distributions and editor override history |
| Memory architecture underdefined — risk of ad hoc implementation | Typed schema, versioned snapshots, and a governed update lifecycle in place |
| Forum reproducibility unclear if context changes between runs | Memory snapshot version stamped in execution metadata; any run replayable |
| No path from debate signal to prompt improvement | Candidate queue → editorial review → approved write → policy proposal chain is live |

---

## Architecture Decisions

### Sequenced after the first complete forum run

Epic 2 is intentionally placed after Epics 1–8 rather than immediately after Epic 1. This is not a deferral — it is the correct sequence. The memory system depends on three upstream contracts that do not exist until the debate engine and evaluation pipeline are built:

1. **Agent prompt structures** (Epic 5) determine the injection format — a memory block must fit naturally into the preparation context without displacing critical paper-grounding material.
2. **Behavioral signals** (Epic 6) determine what is worth storing — the schema categories in §10.5 are only meaningful once real agent debates have been observed.
3. **Evaluation artifact format** (Epic 7) is the direct input to candidate extraction — `extract_memory_candidates()` cannot be correctly implemented until the `evaluation_block` schema is fixed.

Story 2.1 (schema + store) can be written as soon as the schemas are agreed following Epic 7. Stories 2.2–2.6 must follow Epic 7 completion.

### Role-level memory, not instance-level

Memory is shared across all instances of a role (e.g., all Paper Agent instances share one memory store). Instance-specific memory would create divergence between agents playing similar roles across forums and would couple memory to paper content — violating the grounding constraint. Role-level memory contains only behavioral signals, never paper-specific content.

### JSON files on the persistent volume, not a database

Memory stores are JSON files in `/data/workspace/memory/{role}/`. A database is not justified at this stage: the write frequency is once per forum run per role (after editorial review), and the read is once per forum per agent (at preparation). A simple versioned JSON file is auditable, diffable in git, and survives Railway sleep cycles without a separate service. This decision should be revisited if concurrent writes become necessary.

### Candidates are ephemeral; approved snapshots are immutable

Candidate files in `/data/workspace/memory/candidates/{forum_id}/` are deleted after editorial review completes. Approved memory snapshots are never mutated — a new version file is written and the `memory.json` symlink is updated. This preserves the full audit trail and enables snapshot pinning for reproducibility.

### Token budget cap enforced at injection time, not at write time

Memory entries can be verbose in storage. The token budget is applied when building the preparation context block, not when writing to the store. This allows the store to accumulate richer signal while keeping prompt injection lean. The cap is configurable per agent role in forum config.

---

## Stories

---

### Story 2.1 — Memory Store Schema and Persistence Layer

**As a** system,
**I would like** a typed, versioned JSON schema and read/write interface for each agent role's memory store,
**so that** all memory operations are consistent, auditable, and survive Railway sleep cycles.

**Files:**
- NEW: `src/srf/memory/__init__.py`
- NEW: `src/srf/memory/schema.py`
- NEW: `src/srf/memory/store.py`
- NEW: `tests/unit/test_memory_store.py`

**Acceptance Criteria:**

```gherkin
Scenario: memory store initialises with an empty snapshot when no file exists
  Given no memory file exists for role "moderator"
  When  MemoryStore.load(role="moderator") is called
  Then  it returns an empty ModeratorMemory object with version=0

Scenario: memory store loads an existing approved snapshot
  Given a valid memory.json exists for role "challenger" at version 3
  When  MemoryStore.load(role="challenger") is called
  Then  it returns a ChallengerMemory object with version=3 and the stored fields

Scenario: saving a new snapshot increments the version and writes a versioned backup
  Given a ChallengerMemory at version 3
  When  MemoryStore.save(memory) is called
  Then  memory.json reflects version=4
  And   challenger/memory_v3.json contains the prior snapshot (immutable)

Scenario: loading a specific version by number returns that immutable snapshot
  Given memory_v2.json exists for role "synthesis"
  When  MemoryStore.load(role="synthesis", version=2) is called
  Then  it returns the SynthesisMemory at version 2 without altering memory.json

Scenario: memory schema rejects unknown fields on load
  Given a memory.json containing an unrecognised field "hallucinated_field"
  When  MemoryStore.load() is called
  Then  it raises MemorySchemaError naming the unknown field

Scenario: all five role schemas are distinct and non-overlapping
  Given the schema module is imported
  When  the field sets of ModeratorMemory, PaperAgentMemory, ChallengerMemory,
        SynthesisMemory, and EvaluatorMemory are compared
  Then  no field name appears in more than one schema
```

**TDD Notes:** Use `tmp_path` fixture for all file I/O. No Railway volume needed for unit tests. Schema field definitions must be agreed with the team before this story begins — they are informed by the behavioral signals observable in Epics 5–7. Do not invent schema fields; derive them from the real agent outputs produced upstream.

---

### Story 2.2 — Memory Candidate Extraction

**As a** system,
**I would like** the Evaluation Agent to produce structured memory candidates after each forum run,
**so that** behavioral signals are captured in a reviewable form before any editorial decision is made.

**Files:**
- NEW: `src/srf/memory/candidates.py`
- NEW: `tests/unit/test_memory_candidates.py`

**Acceptance Criteria:**

```gherkin
Scenario: candidate extraction produces one candidate file per agent role
  Given a completed forum debate artifact with evaluation scores and behavioral flags
  When  extract_memory_candidates(forum_id, artifact) is called
  Then  five candidate files are written to /data/workspace/memory/candidates/{forum_id}/
  And   each file contains only fields valid for that role's schema

Scenario: candidate file is a MemoryCandidate envelope with status "pending"
  Given a completed debate artifact
  When  extract_memory_candidates is called
  Then  each candidate file has status="pending", forum_id, and a proposed_changes dict

Scenario: proposed_changes contains only high-signal entries above the threshold
  Given a debate where the Challenger used "benchmark skepticism" framing with a low score
  When  extract_memory_candidates is called
  Then  the Challenger candidate's proposed_changes includes a pressure_effectiveness entry
        for that framing pattern

Scenario: extraction is a pure function — calling it twice produces identical candidates
  Given the same debate artifact
  When  extract_memory_candidates is called twice
  Then  both calls produce byte-identical candidate files

Scenario: extraction does not write to the approved memory store
  Given the approved memory store for all roles at version N
  When  extract_memory_candidates is called
  Then  all approved memory stores remain at version N unchanged
```

**TDD Notes:** The input contract for this story — the shape of `debate_artifact.json`'s `evaluation_block`, the list of scoring dimensions, and the definition of "behavioral flags" — is fixed by Epic 7. Do not implement this story against a fabricated artifact shape. Use the canonical artifact schema from Epic 7 as the fixture source.

---

### Story 2.3 — Editorial Approval Interface

**As a** developer,
**I would like** a CLI command that presents pending memory candidates for editorial review and records approve/reject/modify decisions,
**so that** no memory candidate reaches the approved store without a human decision.

**Files:**
- NEW: `src/srf/memory/editorial.py`
- NEW: `scripts/review_memory_candidates.py`
- NEW: `tests/unit/test_memory_editorial.py`

**Acceptance Criteria:**

```gherkin
Scenario: reviewing a candidate with "approve" writes it to the approved store
  Given a pending candidate for role "moderator" with proposed_changes containing one entry
  When  apply_editorial_decision(candidate, decision="approve") is called
  Then  the moderator memory store is updated with the new entry at version N+1
  And   the candidate file status is updated to "approved"

Scenario: reviewing a candidate with "reject" discards it without touching the store
  Given a pending candidate for role "challenger"
  When  apply_editorial_decision(candidate, decision="reject") is called
  Then  the challenger memory store version is unchanged
  And   the candidate file status is updated to "rejected"

Scenario: reviewing a candidate with "modify" applies the edited proposed_changes
  Given a pending candidate with proposed_changes entry A
  When  apply_editorial_decision(candidate, decision="modify", modified_changes={...}) is called
  Then  only the modified_changes are written to the store, not the original proposed_changes

Scenario: the review script exits 1 if any candidates remain in pending status
  Given two candidates exist, one approved and one still pending
  When  review_memory_candidates.py --check-complete is run
  Then  it exits with code 1 and lists the pending role

Scenario: the review script exits 0 when all candidates for a forum are resolved
  Given all five candidates for forum_id "forum-abc" are approved or rejected
  When  review_memory_candidates.py --forum-id forum-abc --check-complete is run
  Then  it exits with code 0
```

**TDD Notes:** The CLI script is tested via subprocess in unit tests — no interactive terminal needed. Use pre-built candidate fixture files.

---

### Story 2.4 — Memory Injection at Preparation

**As a** system,
**I would like** each agent's preparation context to include a token-budgeted memory block drawn from the approved role memory snapshot,
**so that** agents benefit from prior behavioral signals without context bloat.

**Files:**
- NEW: `src/srf/memory/injection.py`
- NEW: `tests/unit/test_memory_injection.py`
- MODIFY: `src/srf/config.py` — add per-role memory token budget config

**Acceptance Criteria:**

```gherkin
Scenario: build_memory_block returns a formatted string within the token budget
  Given an approved ModeratorMemory snapshot with 5 tension_topology entries
  And   the token budget for the moderator role is 300 tokens
  When  build_memory_block(role="moderator", budget_tokens=300) is called
  Then  the returned string encodes to fewer than 300 tokens
  And   it contains at least one entry from tension_topologies

Scenario: build_memory_block returns an empty string when the store has no entries
  Given an empty ModeratorMemory at version 0
  When  build_memory_block(role="moderator", budget_tokens=300) is called
  Then  it returns an empty string without raising

Scenario: entries are prioritised by recency when the budget would be exceeded
  Given a ChallengerMemory with 20 assumption_archetype entries
  And   a budget that fits only 5 entries
  When  build_memory_block is called
  Then  the 5 most recently added entries are included and earlier ones are omitted

Scenario: build_memory_block records the memory snapshot version used
  Given a ChallengerMemory at version 7
  When  build_memory_block(role="challenger", budget_tokens=400) is called
  Then  the returned metadata includes memory_snapshot_version=7

Scenario: memory injection is skipped entirely when no approved snapshot exists
  Given no memory file exists for role "evaluator"
  When  build_memory_block(role="evaluator", budget_tokens=400) is called
  Then  it returns an empty string and memory_snapshot_version=0 in metadata
```

**TDD Notes:** The injection string format must be validated against real agent system prompts from Epic 5. The format chosen here — prose, bullets, YAML, or role-specific narrative — must be agreed before implementation and documented as an Architecture Decision. Token budget defaults must be calibrated against the context windows of the supported LLM providers defined in Epic 1's config.

---

### Story 2.5 — Execution Metadata and Reproducibility Stamping

**As a** system,
**I would like** the memory snapshot version for each agent role to be recorded in the forum's execution metadata,
**so that** any past forum run can be fully reproduced from its config + memory snapshot versions + prompt versions.

**Files:**
- MODIFY: `src/srf/memory/injection.py` — expose snapshot version map
- MODIFY: `src/srf/config.py` — add memory snapshot pinning (optional override)
- NEW: `tests/unit/test_memory_reproducibility.py`

**Acceptance Criteria:**

```gherkin
Scenario: execution metadata contains memory_snapshots field after a forum run
  Given a completed forum preparation phase
  When  the forum's execution_metadata is read from debate_artifact.json
  Then  it contains a "memory_snapshots" dict mapping each role to its snapshot version number

Scenario: pinning a specific memory snapshot version in config forces that version to be loaded
  Given moderator memory at version 5 and version 3 also exists
  And   forum config sets memory_pin.moderator = 3
  When  build_memory_block(role="moderator") is called
  Then  version 3 is loaded and memory_snapshot_version=3 is recorded in metadata

Scenario: two forum runs with identical config and identical snapshot versions produce identical preparation contexts
  Given forum config A and memory snapshots at fixed versions for all roles
  When  the preparation context is built twice with the same inputs
  Then  both builds produce byte-identical memory blocks

Scenario: forum run proceeds normally when memory_snapshots field is absent from config
  Given no memory_pin config is set
  When  build_memory_block is called for all roles
  Then  the current approved snapshot is used for each role without error
```

---

### Story 2.6 — Memory Drift Detection

**As a** developer,
**I would like** a script that compares evaluation score distributions across recent forums against the Evaluator memory baseline,
**so that** unexpected agent behavior drift is detected before it compounds across multiple debates.

**Files:**
- NEW: `scripts/detect_memory_drift.py`
- NEW: `tests/unit/test_memory_drift.py`

**Acceptance Criteria:**

```gherkin
Scenario: script reports no drift when scores are within historical variance
  Given an EvaluatorMemory with score_distributions showing mean=7.2, stddev=0.8 for paper_agent clarity
  And   the last three forums scored 7.0, 7.5, 7.1 on that dimension
  When  detect_memory_drift.py is run
  Then  it exits 0 and reports all dimensions within normal range

Scenario: script reports drift when a dimension exceeds two standard deviations
  Given an EvaluatorMemory with score_distributions showing mean=7.2, stddev=0.8 for challenger pressure
  And   the last forum scored 4.1 on that dimension
  When  detect_memory_drift.py is run
  Then  it exits 1 and names the drifting dimension and agent role

Scenario: script outputs a machine-readable JSON summary
  Given any completed run
  When  detect_memory_drift.py --output json is run
  Then  stdout is a valid JSON object with a "drift_signals" array

Scenario: script exits 0 with a skip message when EvaluatorMemory has fewer than 3 forums of history
  Given an EvaluatorMemory store with score data from only 2 forums
  When  detect_memory_drift.py is run
  Then  it exits 0 and prints "SKIP: insufficient history for drift detection (need 3+)"
```

---

## Implementation Order

```
[After Epic 7 schemas are frozen]
Story 2.1 (schema + store)        ← can begin as soon as Epic 7 evaluation_block format is agreed
  → Story 2.2 (candidate extraction)   ← requires real Epic 7 artifact fixtures
    → Story 2.3 (editorial approval)        parallel with → Story 2.4 (injection)
      → Story 2.5 (reproducibility stamping)
        → Story 2.6 (drift detection)
```

Stories 2.3 and 2.4 can be developed in parallel once 2.2 is complete. Story 2.5 requires 2.4. Story 2.6 requires 2.1. Story 2.1 has an early-start opportunity: it can be written as a schema-only skeleton immediately after Epic 7's evaluation artifact format is agreed — before Epic 7 is fully implemented — so that the schema is available for Epic 7 teams to reference. All other stories must follow Epic 7 completion.

---

## Verification Checklist

```bash
# After 2.1
pytest tests/unit/test_memory_store.py -v

# After 2.2
pytest tests/unit/test_memory_candidates.py -v

# After 2.3
pytest tests/unit/test_memory_editorial.py -v
python scripts/review_memory_candidates.py --help

# After 2.4
pytest tests/unit/test_memory_injection.py -v

# After 2.5
pytest tests/unit/test_memory_reproducibility.py -v

# After 2.6
pytest tests/unit/test_memory_drift.py -v
python scripts/detect_memory_drift.py  # expects SKIP on empty store

# Full epic
pytest tests/unit -v --tb=short -k memory
ruff check src/srf/memory/ scripts/
```

---

## Critical Files

**NEW:**
- `src/srf/memory/__init__.py`
- `src/srf/memory/schema.py`
- `src/srf/memory/store.py`
- `src/srf/memory/candidates.py`
- `src/srf/memory/editorial.py`
- `src/srf/memory/injection.py`
- `scripts/review_memory_candidates.py`
- `scripts/detect_memory_drift.py`
- `tests/unit/test_memory_store.py`
- `tests/unit/test_memory_candidates.py`
- `tests/unit/test_memory_editorial.py`
- `tests/unit/test_memory_injection.py`
- `tests/unit/test_memory_reproducibility.py`
- `tests/unit/test_memory_drift.py`

**MODIFY:**
- `src/srf/config.py` — add per-role memory token budgets and optional snapshot pinning
