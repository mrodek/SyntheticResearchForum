# Epic 6: Debate Engine — Core Discussion Loop

## Prerequisites

- Epic 1 (Foundation) — complete. `SRFConfig`, `log_span`, `build_tracker`, prompt registration all required.
- Epic 5 (Agent Preparation Phase) — complete. `AgentRoster`, `PreparationArtifact`, `ModeratorBriefing`, `ChallengerPreparation`, and `call_provider_directly()` all required.
- Epic 4 (Workspace & Paper Extraction) — complete. `ForumWorkspace`, `PaperContent`, and `srf_forum.yaml` skeleton required.

---

## Context

Preparation produces agents with positions and declared stances. The debate is where those positions are tested. Without a structured discussion loop, the preparation phase produces artifacts that go nowhere. The debate engine is the core of the SRF system: it runs the multi-agent turn-taking loop, enforces hard limits, evaluates every turn for policy violations, and produces the append-only transcript that all downstream phases (synthesis, evaluation, publication) consume.

---

## What We Gain

| Gap (before) | After this epic |
|---|---|
| No debate loop — prepared agents have nowhere to go | Moderator-driven turn loop; agents speak, Guardrail evaluates, Moderator routes |
| No transcript — debate outputs are ephemeral | Append-only JSON transcript written to workspace after every turn |
| No hard limits — debate could run indefinitely | `max_total_turns`, `max_turns_per_agent`, `max_rounds` enforced by orchestrator, not Moderator |
| No content policy enforcement | Guardrail evaluates every turn; CRITICAL signal forces Moderator routing decision |
| No observability for debate turns | `tracker.execute()` auto-creates llm.generation span per turn; `log_tool_call()` per Moderator tool; `log_span()` for guardrail.check |
| Debate step absent from Lobster workflow | `run_debate.py` wired into `srf_forum.yaml`; `debate_workflow.yaml` defines OpenClaw config |

---

## Architecture Decisions

### Moderator owns turn routing; orchestrator owns hard limits

The Moderator decides which agent speaks next and when the debate should close. Hard limits (max turns, max rounds) are enforced by the Python orchestrator independently of the Moderator's preference — when a limit is reached, the orchestrator closes the debate regardless of what the Moderator would have chosen. This prevents prompt injection or Moderator misconfiguration from causing runaway debates.

### Transcript is append-only — one JSON file, one Turn per line (JSON Lines)

Each turn is a self-contained JSON object written as a line to `transcripts/transcript.jsonl`. The file is never rewritten or truncated. If a CRITICAL Guardrail signal fires, the offending turn remains in the transcript with the alert attached as metadata; the Moderator's subsequent routing response is appended as a new turn. This preserves audit integrity.

### Round definition: one turn per agent counts as one round

A round completes when every non-degraded agent has spoken once since the last round boundary. The Moderator is not counted in round tracking. The Challenger counts as one participant. Round boundaries are stored in `DebateState` but are not written to the transcript — they are a routing concept, not a content concept.

### Transcript context is token-budgeted per agent

Full transcripts grow unbounded. Each agent's turn prompt injects the transcript up to `SRF_DEBATE_CONTEXT_TOKENS` characters (default `60000`). When the transcript exceeds the budget, the oldest turns are dropped (summary note prepended). The Moderator receives the full turn count and per-agent turn counts in a structured header regardless of truncation, so routing decisions remain informed.

### Guardrail runs after every turn including the Moderator's

The Guardrail evaluates content policy after every turn, including Moderator routing decisions. A CRITICAL on a Moderator turn forces a re-evaluation at the orchestrator level. Guardrail evaluations are not visible to any agent — they run silently and only surface to the orchestrator and the transcript metadata.

### CRITICAL signal handling: one forced Moderator re-route

When the Guardrail returns CRITICAL on a non-Moderator turn:
1. The offending turn is written to the transcript with `guardrail_signal="critical"` in its metadata.
2. The orchestrator immediately invokes a Moderator turn with `forced_routing=True` in the state.
3. The Moderator is instructed to respond to the CRITICAL signal (it can see the signal reason).
4. Normal routing resumes after the Moderator turn.

The Moderator cannot override or dismiss the CRITICAL forcing. It can only decide the next routing step.

### Agent turn prompts receive preparation artifact, not preparation system prompt

Each Paper Agent's turn prompt passes its `PreparationArtifact` (claimed position, key arguments, anticipated objections) as structured context, not the full preparation system prompt. This keeps turn prompts lean and focused on the current debate state.

### OpenClaw debate_workflow.yaml is the wiring layer only

`debate_workflow.yaml` declares agents, tool bindings, and hard limits. It does not contain logic. All turn execution, tool implementation, and orchestration logic lives in `src/srf/debate/`. The YAML is the configuration contract between Lobster/OpenClaw and the Python implementation.

---

## Stories

---

### Story 6.1 — Debate Transcript Model

**As a** system,
**I would like** a typed transcript model with append-only write semantics,
**so that** every turn is durably recorded in the workspace the moment it is produced, and no downstream phase can receive a partial or corrupted transcript.

**Files:**
- NEW: `src/srf/debate/__init__.py`
- NEW: `src/srf/debate/models.py`
- NEW: `src/srf/debate/transcript.py`
- NEW: `tests/unit/test_debate_transcript.py`

**Acceptance Criteria:**

```gherkin
Scenario: Turn dataclass serialises to and from JSON without data loss
  Given a Turn with all fields populated including guardrail_signal metadata
  When  it is serialised to JSON and deserialised
  Then  the result equals the original Turn

Scenario: append_turn writes a JSON line to the transcript file
  Given an empty transcript file at a workspace path
  When  append_turn(turn, transcript_path) is called
  Then  the file contains exactly one JSON line
  And   deserialising that line produces the original Turn

Scenario: append_turn is atomic — subsequent calls each add one line
  Given a transcript file with 2 existing turns
  When  append_turn(new_turn, transcript_path) is called
  Then  the file contains exactly 3 JSON lines
  And   the first 2 lines are unchanged

Scenario: load_transcript returns turns in append order
  Given a transcript file with 3 turns written in order A, B, C
  When  load_transcript(transcript_path) is called
  Then  it returns a list of 3 Turns in order A, B, C

Scenario: load_transcript returns an empty list for a new transcript file
  Given a transcript path that does not exist
  When  load_transcript(transcript_path) is called
  Then  it returns an empty list without raising

Scenario: Turn with CRITICAL guardrail signal preserves signal metadata on round-trip
  Given a Turn whose metadata contains guardrail_signal="critical" and guardrail_reason="policy violation"
  When  it is serialised and deserialised
  Then  turn.metadata["guardrail_signal"] equals "critical"
  And   turn.metadata["guardrail_reason"] is a non-empty string

Scenario: DebateState tracks turn counts per agent and total
  Given a DebateState after 3 turns: paper-agent-1 twice and paper-agent-2 once
  When  debate_state.turn_count_for("paper-agent-1") is called
  Then  it returns 2
  And   debate_state.total_turns equals 3
```

**TDD Notes:** `append_turn` opens the file in append mode (`"a"`) so concurrent writes from tests don't corrupt the file. Use `tmp_path` for all file operations. `DebateState` is an in-memory dataclass — no file I/O in this story.

---

### Story 6.2 — Moderator Agent

**As a** system,
**I would like** a Moderator agent that takes a debate turn via LLM call and exposes four tools for routing and transcript access,
**so that** the debate loop has a dynamic, context-aware routing controller that can respond to debate state and Guardrail signals.

**Files:**
- NEW: `src/srf/debate/moderator.py`
- NEW: `src/srf/prompts/debate.py`
- NEW: `tests/unit/test_moderator_agent.py`
- MODIFY: `src/srf/prompts/__init__.py`

**Acceptance Criteria:**

```gherkin
Scenario: moderator_turn calls tracker.execute with the moderator_turn prompt name
  Given a ModeratorBriefing, DebateState, and a mock tracker returning a valid tool-call JSON
  When  moderator_turn(briefing, debate_state, transcript, tracker=mock_tracker, config=config, state={"trace_id": "t1"}) is called
  Then  mock_tracker.execute was called once with prompt_name="agent.moderator_turn"
  And   it was called with agent_id="moderator"
  And   state["last_span_id"] is set after the call

Scenario: moderator_turn returns an EnqueueSpeakerDecision when LLM returns enqueue_speaker
  Given a mock tracker whose execute returns '{"tool": "enqueue_speaker", "agent_id": "paper-agent-1", "instruction": "defend your position"}'
  When  moderator_turn(...) is called
  Then  result is an EnqueueSpeakerDecision
  And   result.agent_id equals "paper-agent-1"
  And   result.instruction is a non-empty string

Scenario: moderator_turn returns a CloseDebateDecision when LLM returns close_debate
  Given a mock tracker whose execute returns '{"tool": "close_debate", "reason": "debate exhausted"}'
  When  moderator_turn(...) is called
  Then  result is a CloseDebateDecision
  And   result.reason is a non-empty string

Scenario: log_tool_call is invoked for every tool decision the Moderator returns
  Given a mock tracker and a moderator_turn result of EnqueueSpeakerDecision
  When  moderator_turn(...) is called
  Then  mock_tracker.log_tool_call was called once
  And   it was called with tool_name="moderator.enqueue_speaker"
  And   it was called with parent_span_id equal to state["last_span_id"]

Scenario: moderator_turn raises ModerationError when LLM returns malformed JSON
  Given a mock tracker whose execute returns "not-json"
  When  moderator_turn(...) is called
  Then  it raises ModerationError with a message indicating the parse failure

Scenario: moderator_turn prompt contains required template slots
  Given the prompt named "agent.moderator_turn"
  When  its template is inspected
  Then  it contains "{debate_agenda}", "{transcript_context}", "{turn_counts}", and "{guardrail_context}" slots

Scenario: moderator_turn includes forced_routing context when CRITICAL signal is active
  Given a DebateState with forced_routing=True and a CRITICAL guardrail reason
  And   a mock tracker capturing the messages argument
  When  moderator_turn(...) is called
  Then  the user message contains the CRITICAL signal reason
  And   the user message instructs the Moderator to respond to the alert
```

**TDD Notes:** The Moderator LLM is instructed to return structured JSON selecting one of four tools: `enqueue_speaker`, `read_transcript`, `read_guardrail_signals`, `close_debate`. Parse the JSON and return a typed decision object. `read_transcript` and `read_guardrail_signals` are informational — they return data to the Moderator and trigger another Moderator turn (not a speaker turn). Model the tool result as a `ModerationDecision` union type. Mock `tracker.log_tool_call` with `AsyncMock`.

---

### Story 6.3 — Paper Agent & Challenger Turns

**As a** system,
**I would like** turn functions for Paper Agents and the Challenger that produce a single debate contribution via LLM call,
**so that** each agent can articulate its position in the context of the live debate and respond to what has been said.

**Files:**
- NEW: `src/srf/debate/turns.py`
- MODIFY: `src/srf/prompts/debate.py`
- NEW: `tests/unit/test_debate_turns.py`

**Acceptance Criteria:**

```gherkin
Scenario: paper_agent_turn calls tracker.execute with the paper_turn prompt name
  Given a PreparationArtifact, transcript context, and a mock tracker
  When  paper_agent_turn(agent_id, artifact, transcript, framing_question, tracker=mock_tracker, config=config, state={"trace_id": "t1"}) is called
  Then  mock_tracker.execute was called once with prompt_name="agent.paper_turn"
  And   it was called with agent_id=agent_id
  And   state["last_span_id"] is set after the call

Scenario: paper_agent_turn returns a Turn with the agent's content
  Given a mock tracker whose execute returns a non-empty response_text
  When  paper_agent_turn(...) is called
  Then  result is a Turn
  And   result.speaker_id equals the agent_id
  And   result.role equals "paper_agent"
  And   result.content is a non-empty string

Scenario: paper_agent_turn truncates transcript context to SRF_DEBATE_CONTEXT_TOKENS
  Given a transcript whose serialised text exceeds SRF_DEBATE_CONTEXT_TOKENS characters
  And   a mock tracker that captures the messages argument
  When  paper_agent_turn(...) is called
  Then  the transcript portion of the user message is at most SRF_DEBATE_CONTEXT_TOKENS characters
  And   a WARNING is logged indicating truncation

Scenario: paper_agent_turn injects preparation artifact as structured context
  Given a PreparationArtifact with claimed_position="X" and key_arguments=["A", "B"]
  And   a mock tracker capturing the messages argument
  When  paper_agent_turn(...) is called
  Then  the system message contains "X" from claimed_position
  And   the system message contains "A" and "B" from key_arguments

Scenario: challenger_turn calls tracker.execute with the challenger_turn prompt name
  Given a ChallengerPreparation, transcript context, and a mock tracker
  When  challenger_turn(artifact, transcript, framing_question, tracker=mock_tracker, config=config, state={"trace_id": "t1"}) is called
  Then  mock_tracker.execute was called once with prompt_name="agent.challenger_turn"
  And   it was called with agent_id="challenger"

Scenario: challenger_turn returns a Turn with role "challenger"
  Given a mock tracker returning a non-empty response_text
  When  challenger_turn(...) is called
  Then  result.role equals "challenger"
  And   result.content is a non-empty string

Scenario: paper_agent_turn completes when tracker is None
  Given call_provider_directly returns a non-empty response
  When  paper_agent_turn(agent_id, artifact, transcript, framing_question, tracker=None, config=config, state={}) is called
  Then  it returns a Turn without raising

Scenario: paper_turn prompt contains required template slots
  Given the prompt named "agent.paper_turn"
  When  its template is inspected
  Then  it contains "{claimed_position}", "{key_arguments}", "{transcript_context}", and "{framing_question}" slots
```

**TDD Notes:** Mock `tracker.execute` with `AsyncMock(return_value=ExecutionResult(response_text="...", span_id="span-001", ...))`. Transcript truncation drops the oldest turns first, prepending a note: `"[Transcript truncated — {N} earlier turns omitted]"`. The Paper Agent and Challenger share the same turn infrastructure in `turns.py` but use different prompts and different preparation artifact types.

---

### Story 6.4 — Guardrail Agent

**As a** system,
**I would like** a Guardrail agent that silently evaluates every debate turn for policy violations and returns a structured signal,
**so that** the debate loop has a continuous content policy check that can escalate to the Moderator without disrupting the flow of debate.

**Files:**
- NEW: `src/srf/debate/guardrail.py`
- MODIFY: `src/srf/prompts/debate.py`
- NEW: `tests/unit/test_guardrail_agent.py`

**Acceptance Criteria:**

```gherkin
Scenario: evaluate_turn calls tracker.execute with the guardrail_evaluation prompt name
  Given a Turn and a mock tracker
  When  evaluate_turn(turn, tracker=mock_tracker, config=config, state={"trace_id": "t1"}) is called
  Then  mock_tracker.execute was called once with prompt_name="agent.guardrail_evaluation"
  And   it was called with agent_id="guardrail"

Scenario: evaluate_turn returns a GuardrailEvaluation with signal "ok" for clean content
  Given a mock tracker whose execute returns '{"signal": "ok", "violations_found": 0, "reason": ""}'
  When  evaluate_turn(turn, ...) is called
  Then  result.signal equals "ok"
  And   result.violations_found equals 0

Scenario: evaluate_turn returns signal "critical" for policy-violating content
  Given a mock tracker whose execute returns '{"signal": "critical", "violations_found": 2, "reason": "personal attack"}'
  When  evaluate_turn(turn, ...) is called
  Then  result.signal equals "critical"
  And   result.violations_found equals 2
  And   result.reason equals "personal attack"

Scenario: evaluate_turn logs a guardrail.check span as child of the agent turn span
  Given a mock tracker and state["last_span_id"] = "turn-span-001" before evaluate_turn is called
  When  evaluate_turn(turn, tracker=mock_tracker, config=config, state=state) is called
  Then  mock_tracker.log_span was called once
  And   the submitted SpanPayload has kind equal to "guardrail.check"
  And   the submitted SpanPayload has parent_span_id equal to "turn-span-001"
  And   the submitted SpanPayload has attributes containing violations_found

Scenario: evaluate_turn preserves the agent turn span_id in state after its own execute call
  Given state["last_span_id"] = "turn-span-001" before evaluate_turn
  When  evaluate_turn(turn, tracker=mock_tracker, config=config, state=state) is called
  Then  state["last_span_id"] equals "turn-span-001" after the call
  And   the guardrail.check span is parented to "turn-span-001"

Scenario: evaluate_turn does not raise when PromptLedger log_span returns 5xx
  Given a mock tracker whose log_span raises httpx.HTTPStatusError(status=503)
  When  evaluate_turn(turn, ...) is called
  Then  it returns a GuardrailEvaluation without raising
  And   a WARNING is logged

Scenario: evaluate_turn raises GuardrailError when LLM returns malformed JSON
  Given a mock tracker whose execute returns "not-json"
  When  evaluate_turn(turn, ...) is called
  Then  it raises GuardrailError with a message indicating the parse failure

Scenario: guardrail_evaluation prompt contains required template slots
  Given the prompt named "agent.guardrail_evaluation"
  When  its template is inspected
  Then  it contains "{turn_content}", "{speaker_role}", and "{framing_question}" slots
```

**TDD Notes:** The Guardrail must save the agent turn span ID before calling `tracker.execute()` (which overwrites `state["last_span_id"]`), then restore it for the `log_span()` call. Pattern:
```python
turn_span_id = state.get("last_span_id")
result = await tracker.execute(...)   # overwrites state["last_span_id"]
await tracker.log_span(SpanPayload(
    parent_span_id=turn_span_id,      # parent = the agent turn, not the guardrail LLM
    kind="guardrail.check",
    ...
))
state["last_span_id"] = turn_span_id  # restore for downstream callers
```
The `log_span()` call swallows 5xx — the Guardrail LLM failure (`execute()`) propagates. Mock `tracker.log_span` separately from `tracker.execute`.

---

### Story 6.5 — Debate Loop Orchestration & Lobster Script

**As a** system,
**I would like** a debate orchestrator that drives the full Moderator → Speaker → Guardrail loop with hard limit enforcement, and a Lobster step script that wires it into the forum workflow,
**so that** the debate phase runs end-to-end from the agent preparation output and produces a complete transcript ready for synthesis.

**Files:**
- NEW: `src/srf/debate/orchestrator.py`
- NEW: `workflows/debate_workflow.yaml`
- NEW: `scripts/run_debate.py`
- MODIFY: `workflows/srf_forum.yaml`
- NEW: `tests/unit/test_debate_orchestrator.py`
- NEW: `tests/integration/test_debate_integration.py`

**Acceptance Criteria:**

```gherkin
Scenario: run_debate logs a workflow.phase span at the start of the debate
  Given a valid DebateInput with tracker and state
  When  run_debate(debate_input, tracker=mock_tracker, config=config, state=state) is called
  Then  mock_tracker.log_span was called with kind="workflow.phase" and name="forum.debate"
  And   state["phase_span_id"] is set before any agent turns are taken

Scenario: run_debate invokes Moderator first then the enqueued speaker
  Given mock moderator_turn that returns EnqueueSpeakerDecision(agent_id="paper-agent-1")
  And   mock paper_agent_turn that returns a valid Turn
  When  run_debate(...) is called for one routing cycle
  Then  moderator_turn was called before paper_agent_turn
  And   paper_agent_turn was called with agent_id="paper-agent-1"

Scenario: run_debate calls evaluate_turn after every non-Moderator turn
  Given mock turns that succeed and a mock evaluate_turn returning signal="ok"
  When  run_debate(...) runs two speaker turns
  Then  evaluate_turn was called exactly twice

Scenario: run_debate forces a Moderator turn when Guardrail returns CRITICAL
  Given mock evaluate_turn returning signal="critical" after the first speaker turn
  And   mock moderator_turn capturing state["forced_routing"]
  When  run_debate(...) is called
  Then  the second moderator_turn call receives state with forced_routing=True
  And   the CRITICAL reason is visible in the debate_state passed to moderator_turn

Scenario: run_debate stops when total turns reaches max_total_turns
  Given max_total_turns=3 and mock agents that always succeed
  When  run_debate(...) is called
  Then  the transcript contains exactly 3 non-Moderator turns
  And   debate_state.close_reason equals "max_total_turns_reached"

Scenario: run_debate stops when Moderator returns CloseDebateDecision
  Given mock moderator_turn that returns CloseDebateDecision(reason="consensus reached") after 2 turns
  When  run_debate(...) is called
  Then  the transcript has 2 speaker turns
  And   debate_state.close_reason equals "consensus reached"

Scenario: run_debate excludes degraded agents from speaker queue
  Given an AgentRoster where paper-agent-2 has status="degraded"
  When  run_debate(...) is called
  Then  paper_agent_turn is never called with agent_id="paper-agent-2"

Scenario: run_debate.py script exits 0 and writes transcript path to stdout JSON
  Given valid stdin JSON from agent_preparation step and PROMPTLEDGER_API_URL configured
  When  scripts/run_debate.py is run
  Then  it exits with code 0
  And   stdout JSON contains transcript_path and turn_count

Scenario: srf_forum.yaml debate step is wired to run debate_workflow.yaml
  Given the file workflows/srf_forum.yaml
  When  it is parsed as YAML
  Then  the step named "debate" uses run: openclaw run workflows/debate_workflow.yaml
  And   it uses stdin: $agent_preparation.json
```

**TDD Notes:** The orchestrator loop is the most complex unit in this epic — test the loop logic with fully mocked agent functions. The `max_total_turns` test must assert the loop terminates without the test timing out (use a loop counter, not real time). The integration test requires `SRF_LLM_PROVIDER` and either `PROMPTLEDGER_API_URL` or `tracker=None`; skip when absent. `debate_workflow.yaml` declares the OpenClaw agent config — it does not need to be parsed by Python unit tests, only by OpenClaw at runtime. Verify its structure with a YAML parse check in the verification checklist.

---

## Implementation Order

```
Story 6.1 (transcript model — no dependencies beyond Epic 1 models)
  → Story 6.2 (Moderator — depends on DebateState from 6.1)
  → Story 6.3 (Paper Agent & Challenger turns — depends on Turn from 6.1)
  → Story 6.4 (Guardrail — depends on Turn from 6.1)
    → Story 6.5 (debate loop — depends on 6.1, 6.2, 6.3, 6.4)
```

Stories 6.2, 6.3, and 6.4 depend only on 6.1 and can be developed in parallel.

---

## Verification Checklist

```bash
# After 6.1
pytest tests/unit/test_debate_transcript.py -v

# After 6.2
pytest tests/unit/test_moderator_agent.py -v
python -c "from srf.prompts.debate import DEBATE_PROMPTS; print([p['name'] for p in DEBATE_PROMPTS])"
# Expects: ['agent.moderator_turn']

# After 6.3
pytest tests/unit/test_debate_turns.py -v
python -c "from srf.prompts.debate import DEBATE_PROMPTS; print([p['name'] for p in DEBATE_PROMPTS])"
# Expects: ['agent.moderator_turn', 'agent.paper_turn', 'agent.challenger_turn']

# After 6.4
pytest tests/unit/test_guardrail_agent.py -v
python -c "from srf.prompts.debate import DEBATE_PROMPTS; print([p['name'] for p in DEBATE_PROMPTS])"
# Expects: [..., 'agent.guardrail_evaluation']

# After 6.5
pytest tests/unit/test_debate_orchestrator.py -v
python -c "import yaml; w = yaml.safe_load(open('workflows/srf_forum.yaml')); s = next(s for s in w['steps'] if s['name']=='debate'); print(s['run'])"
# Expects: openclaw run workflows/debate_workflow.yaml
python -c "import yaml; yaml.safe_load(open('workflows/debate_workflow.yaml')); print('debate_workflow.yaml is valid YAML')"

# Full epic suite
pytest tests/unit -v --tb=short
ruff check src/ tests/ scripts/

# With live LLM provider:
pytest tests/integration/test_debate_integration.py -v
```

---

## Critical Files

**NEW:**
- `src/srf/debate/__init__.py`
- `src/srf/debate/models.py`
- `src/srf/debate/transcript.py`
- `src/srf/debate/moderator.py`
- `src/srf/debate/turns.py`
- `src/srf/debate/guardrail.py`
- `src/srf/debate/orchestrator.py`
- `src/srf/prompts/debate.py`
- `workflows/debate_workflow.yaml`
- `scripts/run_debate.py`
- `tests/unit/test_debate_transcript.py`
- `tests/unit/test_moderator_agent.py`
- `tests/unit/test_debate_turns.py`
- `tests/unit/test_guardrail_agent.py`
- `tests/unit/test_debate_orchestrator.py`
- `tests/integration/test_debate_integration.py`

**MODIFY:**
- `src/srf/prompts/__init__.py`
- `workflows/srf_forum.yaml` _(debate step wired)_
- `Requirements/progress_summary.md`
