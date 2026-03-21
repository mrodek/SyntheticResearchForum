# Epic 6B: Debate Engine — OpenClaw Native

## Prerequisites

- Epic 5 (Agent Preparation Phase) — complete. `PreparationArtifact`, `ModeratorBriefing`, `ChallengerPreparation`, and workspace layout under `/data/workspace/forum/{forum_id}/preparation/` all required.
- Epic 4 (Workspace & Paper Extraction) — complete. `state.json` workspace format required.
- Epic 1 (Foundation) — complete. `SRFConfig` and structlog required.

---

## Context

Epic 6 (Python-first) planned to build a Python orchestrator that reimplements what OpenClaw already does natively: multi-agent session management, turn routing, subagent spawning, and tool-mediated state access. That is roughly 1,500 lines of Python across ten new files before a single debate turn executes. OpenClaw was designed to run exactly this kind of structured multi-agent exchange. This epic replaces the Python orchestrator with a richly specified OpenClaw skill and a minimal bridge script, keeping Python where it genuinely earns its place — context preparation and transcript validation — and delegating the debate loop itself to the runtime.

---

## What We Gain

| Gap (before) | After this epic |
|---|---|
| No debate loop | OpenClaw skill drives a complete Moderator → Speaker → Guardrail loop |
| ~1,500 lines of Python orchestration code | ~200 lines of Python (context prep + bridge + validator) |
| Complex Python unit tests for routing logic that can only truly be validated live | Testable inputs and outputs; live smoke test verifies the loop |
| Debate structure locked into Python classes | Skill instructions can be updated without a code deploy |
| 5 stories across 6 weeks to implement Epic 6 | 4 stories implementable in 1 week |
| Lobster step calls Python that reimplements agent orchestration | Lobster step calls bridge script that triggers OpenClaw native debate session |

---

## Architecture Decisions

### The debate loop runs inside OpenClaw, not inside a Python script

The `debate` Lobster step calls `scripts/run_debate_bridge.py`. The bridge script reads the prepared workspace, calls the OpenClaw `/hooks/agent` endpoint to trigger a `run_forum_debate` skill session, then polls the workspace for the completed transcript. When the transcript is present and closed, the bridge script returns transcript metadata to Lobster and exits 0. The Python script's only job is triggering and waiting — it contains no debate logic.

### OpenClaw orchestrates turns via its native subagent system

The `run_forum_debate` skill instructs the main session to act as the orchestrator (Moderator role). For each speaker turn, the orchestrator spawns a subagent pre-loaded with:
- The role's system prompt
- The agent's `PreparationArtifact` as structured context
- The current transcript up to `SRF_DEBATE_CONTEXT_TOKENS` characters

The subagent produces one turn and exits. The orchestrator writes it to the transcript and routes the next turn. This preserves clean role separation — Paper Agent 1 never sees Paper Agent 1's preparation artifact leaking into Paper Agent 2's reasoning.

### Guardrail evaluation is an inline LLM call by the orchestrator, not a subagent

The Guardrail does not generate debate content. It evaluates content that already exists. Running it as a subagent adds overhead without benefit. The orchestrator makes a direct LLM call after each speaker turn, receives a structured signal, and decides whether to force a Moderator re-route.

### Transcript is JSONL written to the workspace volume by the orchestrator

Each turn is a JSON object appended as a line to `transcripts/transcript.jsonl`. The orchestrator is explicitly instructed: never overwrite a line, never truncate the file, always append. The append-only property is enforced by instruction, not by file locking — the single-session model means there is no concurrent writer to protect against.

When the debate closes, the orchestrator writes a final `debate_closed` sentinel line to the transcript. The bridge script polls for this sentinel to know the debate is done.

### Hard limits are passed as numeric instructions, not as environment variables read by Python

`max_total_turns`, `max_turns_per_agent`, and `max_rounds` travel from `state.json` into `debate_context.json` (written by the bridge script) and are embedded in the skill invocation message. The orchestrator counts turns and enforces them. No Python counting logic is needed.

### Role definitions live in skill documents, not in Python prompt strings

`MODERATOR.md`, `PAPER_AGENT.md`, `CHALLENGER.md`, and `GUARDRAIL.md` are loaded by the skill as context documents. Updating a role definition requires updating a Markdown file and redeploying, not editing Python, running tests, and cutting a release. Prompt governance (via `validate_prompts.py`) still applies — these files are the prompt definitions.

### Epic 6 (Python-first) is superseded, not deleted

`srf_epic_06_debate_engine.md` is retained as a reference. If the OpenClaw-native approach fails to meet quality or observability requirements after a complete run, Epic 6 is the fallback. The two approaches share the same transcript format and the same workspace layout, so switching back does not require migrating data.

---

## Stories

---

### Story 6B.1 — Debate Context Document

**As a** system,
**I would like** a `debate_context.json` document written to the forum workspace before the debate begins,
**so that** the OpenClaw skill session has a single, validated starting point containing every input it needs to run the debate without querying other systems.

**Context:** The skill session starts with a message containing the debate_context.json path. Everything it needs — forum config, agent roster, preparation artifact paths, hard limits, transcript path — is in that one document. If the document is malformed or incomplete, the debate cannot start. Validating it in Python before handing off to OpenClaw catches problems early.

**Files:**
- NEW: `scripts/prepare_debate_context.py`
- NEW: `tests/unit/test_prepare_debate_context.py`

**Acceptance Criteria:**

```gherkin
Scenario: prepare_debate_context writes a well-formed JSON document to the workspace
  Given a forum workspace with state.json, 2 preparation artifacts, a moderator briefing, and a challenger preparation
  When  prepare_debate_context(forum_id, workspace_root) is called
  Then  debate_context.json is written to /data/workspace/forum/{forum_id}/
  And   it contains forum_id, framing_question, topic, tension_axis

Scenario: debate_context includes one entry per ready agent with artifact path
  Given a forum workspace with 2 ok Paper Agents, 1 degraded Paper Agent, a Moderator, and a Challenger
  When  prepare_debate_context is called
  Then  debate_context["agents"] contains 4 entries (2 paper agents + moderator + challenger)
  And   each ok Paper Agent entry has artifact_path pointing to an existing file
  And   the degraded Paper Agent entry has status "degraded" and no artifact_path

Scenario: debate_context includes hard limits from forum config
  Given a state.json containing max_total_turns=30, max_turns_per_agent=8, max_rounds=4
  When  prepare_debate_context is called
  Then  debate_context["limits"]["max_total_turns"] equals 30
  And   debate_context["limits"]["max_turns_per_agent"] equals 8
  And   debate_context["limits"]["max_rounds"] equals 4

Scenario: debate_context includes transcript_path and closed_sentinel
  Given a forum workspace for forum_id "forum-abc"
  When  prepare_debate_context is called
  Then  debate_context["transcript_path"] equals the expected transcripts/transcript.jsonl path
  And   debate_context["closed_sentinel"] equals "DEBATE_CLOSED"

Scenario: prepare_debate_context raises DebateContextError when fewer than 2 ok Paper Agents exist
  Given a forum workspace where only 1 Paper Agent has status "ok"
  When  prepare_debate_context is called
  Then  it raises DebateContextError with a message indicating insufficient agents

Scenario: prepare_debate_context raises DebateContextError when a required preparation artifact is missing
  Given a forum workspace where Paper Agent 1 has status "ok" but its artifact file does not exist
  When  prepare_debate_context is called
  Then  it raises DebateContextError naming the missing artifact path
```

**TDD Notes:** All file I/O uses `tmp_path`. Build minimal fixture factory functions for `state.json` and preparation artifact JSON files. `DebateContextError` is a new exception class in this script (no source module dependency — this script is standalone). Do not import from `srf.debate` — that package does not exist in this epic.

---

### Story 6B.2 — Forum Debate Skill

**As a** system,
**I would like** a richly specified OpenClaw skill that runs the complete multi-agent debate when invoked with a `debate_context.json` path,
**so that** OpenClaw's native agent runtime handles turn orchestration, role separation, and content evaluation without any Python orchestration logic.

**Context:** This is the core deliverable of the epic. The skill is not a thin wrapper — it is the complete specification of how the debate runs. It tells OpenClaw exactly what the Moderator does, what a Paper Agent does, how to evaluate content, when to close, and what to write to the transcript. The quality of the debate is determined by the quality of this specification.

**Files:**
- NEW: `skills/run_forum_debate/SKILL.md`
- NEW: `skills/run_forum_debate/MODERATOR.md`
- NEW: `skills/run_forum_debate/PAPER_AGENT.md`
- NEW: `skills/run_forum_debate/CHALLENGER.md`
- NEW: `skills/run_forum_debate/GUARDRAIL.md`
- NEW: `tests/unit/test_debate_skill_documents.py`

**Acceptance Criteria:**

```gherkin
Scenario: SKILL.md contains all required structural sections
  Given the file skills/run_forum_debate/SKILL.md
  When  its content is parsed
  Then  it contains sections: "Parameters", "Inputs", "Debate Phases", "Turn Protocol", "Transcript Format", "Hard Limits", "Closing Protocol"

Scenario: SKILL.md references all four role documents
  Given the file skills/run_forum_debate/SKILL.md
  When  its content is parsed
  Then  it references MODERATOR.md, PAPER_AGENT.md, CHALLENGER.md, and GUARDRAIL.md by name

Scenario: each role document defines the role's goal, constraints, and output format
  Given each of MODERATOR.md, PAPER_AGENT.md, CHALLENGER.md, GUARDRAIL.md
  When  each file's content is parsed
  Then  each contains a "Role" section, a "Constraints" section, and an "Output Format" section

Scenario: SKILL.md specifies the exact JSON structure for a transcript turn
  Given the file skills/run_forum_debate/SKILL.md
  When  its Transcript Format section is parsed
  Then  it specifies required fields: turn_id, speaker_id, role, phase, content, timestamp

Scenario: SKILL.md specifies the DEBATE_CLOSED sentinel line format
  Given the file skills/run_forum_debate/SKILL.md
  When  its Closing Protocol section is parsed
  Then  it specifies a sentinel JSON line containing "type": "DEBATE_CLOSED" and "reason"

Scenario: SKILL.md instructs the orchestrator to enforce hard limits
  Given the file skills/run_forum_debate/SKILL.md
  When  its Hard Limits section is parsed
  Then  it states that when max_total_turns is reached the debate must close regardless of Moderator preference
  And   it states that degraded agents must be excluded from the speaker queue

Scenario: GUARDRAIL.md specifies three signal levels and what each triggers
  Given the file skills/run_forum_debate/GUARDRAIL.md
  When  its content is parsed
  Then  it defines signal levels "ok", "warning", and "critical"
  And   it specifies that "critical" forces an immediate Moderator re-routing turn
```

**TDD Notes:** These tests verify document structure, not LLM behavior. Parse with `re.search` for section headings and key phrases. Keep assertions focused on the presence of structural requirements — do not assert exact prose wording. A separate live smoke test (Story 6B.4) validates that the skill actually runs.

---

### Story 6B.3 — Transcript Validator

**As a** system,
**I would like** a transcript validator that reads the completed `transcript.jsonl` and confirms it is well-formed, append-only, and contains the required structural elements,
**so that** the synthesis phase never receives a malformed or incomplete transcript.

**Context:** The validator runs after the debate completes, before synthesis begins. It is the contract boundary between OpenClaw's output and the Python synthesis pipeline. If the transcript is malformed, the validator raises an error and prevents synthesis from producing garbage output.

**Files:**
- NEW: `scripts/validate_transcript.py`
- NEW: `tests/unit/test_validate_transcript.py`

**Acceptance Criteria:**

```gherkin
Scenario: validate_transcript returns a TranscriptSummary for a well-formed transcript
  Given a transcript.jsonl with 6 valid turns followed by a DEBATE_CLOSED sentinel
  When  validate_transcript(transcript_path) is called
  Then  it returns a TranscriptSummary with turn_count=6, debate_status="closed", close_reason non-empty

Scenario: validate_transcript raises TranscriptError when the DEBATE_CLOSED sentinel is absent
  Given a transcript.jsonl with 4 turns and no sentinel line
  When  validate_transcript is called
  Then  it raises TranscriptError with a message indicating the debate did not close cleanly

Scenario: validate_transcript raises TranscriptError when any line is not valid JSON
  Given a transcript.jsonl where line 3 is malformed JSON
  When  validate_transcript is called
  Then  it raises TranscriptError identifying line 3 as the malformed entry

Scenario: validate_transcript raises TranscriptError when a turn is missing required fields
  Given a transcript.jsonl where one turn lacks the "speaker_id" field
  When  validate_transcript is called
  Then  it raises TranscriptError naming the missing field and the turn_id

Scenario: validate_transcript returns speaker breakdown in TranscriptSummary
  Given a transcript with 3 turns from paper-agent-1, 2 from paper-agent-2, 1 from challenger
  When  validate_transcript is called
  Then  summary.turns_by_speaker["paper-agent-1"] equals 3
  And   summary.turns_by_speaker["challenger"] equals 1

Scenario: validate_transcript raises TranscriptError when transcript file does not exist
  Given a path to a transcript file that does not exist
  When  validate_transcript is called
  Then  it raises TranscriptError indicating the file is absent
```

**TDD Notes:** Build a fixture helper `_write_transcript(tmp_path, turns, closed=True)` that writes a well-formed JSONL file. All tests use `tmp_path`. `TranscriptSummary` is a dataclass defined in `validate_transcript.py`. `TranscriptError` is a local exception class — no dependency on `srf.debate`.

---

### Story 6B.4 — Bridge Script & Pipeline Integration

**As a** system,
**I would like** a bridge script that triggers the `run_forum_debate` OpenClaw skill session and waits for the transcript to close, and a Lobster step that wires it into the forum workflow,
**so that** the debate phase runs automatically as part of the pipeline and hands a validated transcript to the synthesis phase.

**Files:**
- NEW: `scripts/run_debate_bridge.py`
- MODIFY: `workflows/srf_forum.yaml`
- NEW: `tests/unit/test_run_debate_bridge.py`

**Acceptance Criteria:**

```gherkin
Scenario: run_debate_bridge.py calls prepare_debate_context before triggering OpenClaw
  Given valid stdin JSON from the agent_preparation Lobster step
  And   a mock OpenClaw API that accepts the trigger call
  When  run_debate_bridge.py runs
  Then  prepare_debate_context was called with the forum_id from stdin
  And   debate_context.json exists in the forum workspace before the API call is made

Scenario: run_debate_bridge.py exits 0 and writes transcript metadata to stdout JSON
  Given a mock that returns a well-formed closed transcript after one poll cycle
  When  run_debate_bridge.py runs
  Then  it exits with code 0
  And   stdout JSON contains forum_id, transcript_path, turn_count, and debate_status

Scenario: run_debate_bridge.py exits 1 when the transcript does not close within the timeout
  Given a mock OpenClaw API that accepts the trigger
  And   the transcript never receives a DEBATE_CLOSED sentinel within the timeout
  When  run_debate_bridge.py runs with poll_timeout_seconds=5
  Then  it exits with code 1
  And   stderr contains a message indicating timeout waiting for debate to close

Scenario: run_debate_bridge.py exits 1 when validate_transcript raises TranscriptError
  Given a mock that writes a malformed transcript
  When  run_debate_bridge.py runs
  Then  it exits with code 1
  And   stderr contains the TranscriptError message

Scenario: srf_forum.yaml debate step uses run_debate_bridge.py
  Given the file workflows/srf_forum.yaml parsed as YAML
  When  the step with id "debate" is inspected
  Then  its command contains "run_debate_bridge.py"
  And   its stdin references "$agent_preparation.json"

Scenario: run_debate_bridge.py passes OPENCLAW_GATEWAY_TOKEN in the Authorization header
  Given OPENCLAW_GATEWAY_TOKEN is set in the environment
  And   a mock HTTP server capturing request headers
  When  run_debate_bridge.py triggers the OpenClaw API
  Then  the Authorization header equals "Bearer <OPENCLAW_GATEWAY_TOKEN>"
```

**TDD Notes:** Mock the OpenClaw HTTP API with `unittest.mock.patch("requests.post")` and a polling mock that returns the sentinel on the second poll. Use `tmp_path` for all workspace file creation. Test the polling logic with a short `poll_interval_seconds=0.01` to avoid slow tests. The integration smoke test (below) is the live validation — unit tests cover the bridge logic only.

---

## What to Put in the Skill Documents

### SKILL.md — the orchestration contract

The skill is triggered with a single parameter: `context_path` — the absolute path to `debate_context.json`. The skill session:

1. **Loads context** — reads `debate_context.json`, prints a brief summary to confirm it loaded correctly
2. **Loads role documents** — reads MODERATOR.md, PAPER_AGENT.md, CHALLENGER.md, GUARDRAIL.md
3. **Initialises the transcript** — confirms `transcript.jsonl` does not exist yet (or is empty), then begins appending
4. **Opens the debate** — writes a `debate_opened` header line to the transcript with forum_id, topic, framing question, and agent roster
5. **Runs the debate loop** — see Turn Protocol below
6. **Closes the debate** — writes the `DEBATE_CLOSED` sentinel line; exits

### Turn Protocol (embedded in SKILL.md)

```
LOOP until close condition:

  MODERATOR TURN:
  - Spawn subagent: system=MODERATOR.md + current transcript context + agent roster + turn counts
  - Subagent returns: JSON { "next_speaker": "<agent_id>", "instruction": "<guidance>" }
    OR: { "action": "close", "reason": "<why>" }
  - If close: write sentinel, exit loop
  - Write Moderator routing decision as a transcript line (role="moderator", content=instruction)

  SPEAKER TURN:
  - Identify agent from next_speaker
  - If agent is degraded: skip, log warning, force Moderator re-route
  - Spawn subagent:
    system = [role document for this agent] + [preparation artifact JSON]
    user   = [framing question] + [current transcript, truncated to SRF_DEBATE_CONTEXT_TOKENS chars]
             + [Moderator instruction for this turn]
  - Subagent returns: the turn content (plain prose — no JSON wrapping required)
  - Write turn to transcript.jsonl: { turn_id, speaker_id, role, phase, content, timestamp }

  GUARDRAIL CHECK (inline — not a subagent):
  - LLM call: evaluate the just-written turn for violations
  - Prompt: GUARDRAIL.md + turn content + framing question
  - Response must be JSON: { "signal": "ok"|"warning"|"critical", "reason": "" }
  - If "critical": set forced_routing=true, include reason in next Moderator context
  - If "warning": log warning in transcript metadata, continue normally
  - If "ok": continue

  LIMIT CHECK:
  - If total_turns >= max_total_turns: close with reason "max_total_turns_reached"
  - If any agent's turn_count >= max_turns_per_agent: exclude from future turns
  - If round_count >= max_rounds: close with reason "max_rounds_reached"
```

### Debate Phases (embedded in SKILL.md)

The Moderator is instructed to sequence the debate through five phases. Phase transitions are signalled in the Moderator's routing decisions and reflected in each turn's `phase` field:

| Phase | Moderator goal | Ends when |
|---|---|---|
| `opening` | Each agent states its claimed position; no cross-examination yet | All agents have spoken once |
| `position` | Each agent develops its core argument in depth | Each agent has spoken twice total |
| `challenge` | Challenger applies structured pressure; agents defend | Challenger has spoken at least twice |
| `discussion` | Open cross-examination; Moderator routes to maximise intellectual tension | Moderator judges exhaustion or limit reached |
| `closing` | Each agent states what changed and what didn't | All agents have given a closing statement |

The Moderator is not required to complete every phase — if limits are reached or the debate closes early, it closes at whatever phase it is in.

### Role Inputs per Agent Type

**Moderator:**
- Full transcript context
- Turn counts per agent and total
- Guardrail signals (warning + critical history)
- Forced routing flag + critical reason if active
- Framing question and topic
- Agent roster with status (ok/degraded)

**Paper Agent:**
- Own `PreparationArtifact`: claimed_position, key_arguments, anticipated_objections, epistemic_confidence
- Own paper abstract (truncated if long)
- Current transcript context (truncated to SRF_DEBATE_CONTEXT_TOKENS)
- Framing question
- Moderator's instruction for this turn
- **NOT** other agents' preparation artifacts — isolation is deliberate

**Challenger:**
- Own `ChallengerPreparation`: pressure_axes, identified_tensions, planned_interventions
- Full agent roster with paper titles (but not their preparation artifacts)
- Current transcript context
- Framing question
- Moderator's instruction

**Guardrail (inline evaluation):**
- Turn content
- Speaker role
- Framing question
- Evaluation criteria: fabricated evidence, grounding violations, personal attacks, evasion, epistemic bad faith

### Transcript JSON Line Format

Every speaker turn written to `transcript.jsonl`:

```json
{
  "turn_id": "t-0001",
  "speaker_id": "paper-agent-1",
  "role": "paper_agent",
  "phase": "position",
  "content": "...",
  "timestamp": "2026-03-21T15:30:00Z",
  "metadata": {
    "guardrail_signal": "ok",
    "guardrail_reason": "",
    "moderator_instruction": "Defend your position on retrieval..."
  }
}
```

Moderator routing turns use `role: "moderator"` and `content` contains the instruction given to the next speaker (not the routing decision JSON).

Closing sentinel:

```json
{"type": "DEBATE_CLOSED", "reason": "max_total_turns_reached", "total_turns": 30, "timestamp": "..."}
```

---

## Implementation Order

```
Story 6B.1 (debate context document — no dependencies)
  → Story 6B.2 (skill documents — depends on context format from 6B.1)
  → Story 6B.3 (transcript validator — depends on transcript format from 6B.2)
    → Story 6B.4 (bridge script — depends on 6B.1 prepare_debate_context, 6B.3 validate_transcript)
```

Stories 6B.2 and 6B.3 can be developed in parallel after 6B.1.

---

## Verification Checklist

```bash
# After 6B.1
pytest tests/unit/test_prepare_debate_context.py -v

# After 6B.2
pytest tests/unit/test_debate_skill_documents.py -v
# Manually inspect: does the SKILL.md read like a complete specification?
# Check: do the role documents give enough context to run without guessing?

# After 6B.3
pytest tests/unit/test_validate_transcript.py -v

# After 6B.4
pytest tests/unit/test_run_debate_bridge.py -v
python -c "import yaml; w = yaml.safe_load(open('workflows/srf_forum.yaml')); s = next(s for s in w['steps'] if s['id']=='debate'); print(s['command'])"
# Expects: python scripts/run_debate_bridge.py

# Full unit suite
pytest tests/unit -v --tb=short
ruff check src/ tests/ scripts/ skills/

# Live smoke test (requires Railway service + live LLM):
# 1. Run full pipeline through agent_preparation (already tested)
# 2. Trigger run_debate_bridge.py with the forum_id
# 3. Verify transcript.jsonl appears with >= 6 turns and a DEBATE_CLOSED sentinel
# 4. Verify validate_transcript passes on the produced transcript
# 5. Inspect transcript.md (human-readable version) for debate quality
```

---

## Critical Files

**NEW:**
- `scripts/prepare_debate_context.py`
- `scripts/validate_transcript.py`
- `scripts/run_debate_bridge.py`
- `skills/run_forum_debate/SKILL.md`
- `skills/run_forum_debate/MODERATOR.md`
- `skills/run_forum_debate/PAPER_AGENT.md`
- `skills/run_forum_debate/CHALLENGER.md`
- `skills/run_forum_debate/GUARDRAIL.md`
- `tests/unit/test_prepare_debate_context.py`
- `tests/unit/test_validate_transcript.py`
- `tests/unit/test_run_debate_bridge.py`
- `tests/unit/test_debate_skill_documents.py`

**MODIFY:**
- `workflows/srf_forum.yaml` _(debate step: `run_debate.py` → `run_debate_bridge.py`)_
- `Requirements/progress_summary.md`

**NOT NEEDED (eliminates from Epic 6):**
- `src/srf/debate/` — entire Python package (not created)
- `src/srf/prompts/debate.py` — prompts live in skill documents
- `workflows/debate_workflow.yaml` — replaced by skill
- Six Python test files for debate infrastructure
