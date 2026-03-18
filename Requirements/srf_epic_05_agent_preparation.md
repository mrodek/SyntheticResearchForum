# Epic 5: Agent Preparation Phase

## Prerequisites

- Epic 1 (Foundation) — complete. `SRFConfig`, `log_span`, `build_tracker`, prompt registration all required.
- Epic 3 (Newsletter Parsing) — complete. `CandidateForumConfig` and the `call_provider_directly()` fallback pattern established.
- Epic 4 (Workspace & Paper Extraction) — complete. `ForumWorkspace`, `PaperContent`, and `workflows/srf_forum.yaml` skeleton all required.

---

## Context

A debate without preparation is noise. Before the first turn is spoken, each agent must have read its assigned material, formed a position, and anticipated the intellectual terrain. The Preparation Phase is where agents transition from generic LLM instances into forum participants with defined roles, specific knowledge, and declared stances. It is also the first injection point for agent memory — the behavioural context that accumulates across forum runs. This epic builds the LLM client abstraction that all subsequent epics depend on, then implements the preparation calls for all three agent types that prepare: Paper Agents, the Moderator, and the Challenger.

---

## What We Gain

| Gap (before) | After this epic |
|---|---|
| No fallback for tracker=None local execution | `call_provider_directly(messages, config)` — thin fallback used only when `tracker=None`; primary path is always `tracker.execute()` |
| No agent identity — papers assigned nowhere | `AgentRoster` assigns Paper Agents to papers, names them, defines the Moderator and Challenger |
| Agents enter the debate cold | Each Paper Agent produces a `PreparationArtifact` with position, arguments, and anticipated objections |
| Moderator enters blind to the paper landscape | Moderator receives a structured briefing: debate agenda, agent profiles, escalation policy |
| Challenger has no declared angle | Challenger preparation defines skeptical stance and challenge axes before the debate opens |
| Memory injection point undefined | `{memory_block}` slot in all preparation prompts; empty string injected now, Epic 2 populates it |
| Parallel preparation unimplemented | `run_preparation.py` fans out via `asyncio.gather()` with retry and degraded-agent policy |

---

## Architecture Decisions

### All LLM calls route through tracker.execute() — call_provider_directly() is the tracker=None fallback only

Every agent preparation LLM call uses `tracker.execute(prompt_name, messages, mode="mode2", state, agent_id)`. PromptLedger makes the provider call and auto-creates the span. `call_provider_directly(messages, config)` exists solely for the `tracker=None` fallback path (offline development, unit tests without a PL instance). No production code path calls provider SDKs directly when `tracker is not None`. The provider SDKs (`anthropic`, `openai`) are installed as optional dependencies and only imported inside `call_provider_directly()` — no other module imports them.

### Paper text is token-budgeted before injection

Full academic papers can exceed 80 pages. The preparation prompt injects paper text up to `SRF_PAPER_TOKEN_BUDGET` characters (default `80000` ≈ 20k tokens). When truncation occurs, a WARNING is logged with the paper `arxiv_id` and the character count dropped. The truncation point is the end of a sentence boundary, not mid-word. Moderator and Challenger receive abstract + introduction + conclusion only — they do not need the full body.

### `{memory_block}` slot in all preparation prompts — empty string now, Epic 2 populates it

Every preparation prompt template contains a `{memory_block}` interpolation slot. In this epic it always receives an empty string. This contract is established now so Epic 2 can inject memory without modifying prompt templates. Unit tests assert the slot exists in every preparation prompt.

### Preparation artifacts are write-once

Once a `PreparationArtifact` is written to `preparation/{agent_id}/artifact.json`, it is never modified. If preparation is retried (after failure), a new artifact replaces the previous one only if the retry succeeds. Partial or failed artifacts are written with `status="failed"` and never used by the debate phase.

### Moderator failure aborts; Challenger failure degrades gracefully

The Moderator is the routing control plane — without a Moderator briefing, the debate cannot proceed. Moderator preparation failure aborts the forum after exhausting retries. The Challenger is valuable but not structurally required — if Challenger preparation exhausts retries, the forum proceeds without a Challenger and logs a WARNING. The agent roster marks the Challenger as `status="degraded"`.

### Paper Agent identity: `paper-agent-{N}`, not paper title

Agent IDs are stable, short, and role-scoped: `paper-agent-1`, `paper-agent-2`, `paper-agent-3`. They are assigned in the order papers appear in the approved config. This keeps IDs predictable across retries and makes logs scannable. Display names for the debate transcript (Epic 6) are derived from the paper title at render time.

---

## Stories

---

### Story 5.1 — Provider Fallback Client

**As a** system,
**I would like** a `call_provider_directly()` function that calls the configured LLM provider without PromptLedger,
**so that** agent preparation can proceed in tracker=None contexts (offline development, CI without PL credentials) using the same provider config that production uses.

**Context:** The primary execution path for all LLM calls is `tracker.execute()` — PromptLedger makes the provider call and auto-creates the span. `call_provider_directly()` is the fallback used only when `tracker is None`. It must accept the same `messages` format and return a plain `str`. It never logs spans. It is never called when `tracker is not None`.

**Files:**
- NEW: `src/srf/llm/__init__.py`
- NEW: `src/srf/llm/fallback.py`
- NEW: `tests/unit/test_llm_fallback.py`
- NEW: `tests/integration/test_llm_fallback_integration.py`

**Acceptance Criteria:**

```gherkin
Scenario: call_provider_directly returns response text when SRF_LLM_PROVIDER is "anthropic"
  Given SRFConfig with llm_provider="anthropic" and a mock Anthropic SDK returning "Hello"
  When  call_provider_directly(messages=[{"role": "user", "content": "hi"}], config=config) is called
  Then  the returned string equals "Hello"

Scenario: call_provider_directly returns response text when SRF_LLM_PROVIDER is "openai"
  Given SRFConfig with llm_provider="openai" and a mock OpenAI SDK returning "Hello"
  When  call_provider_directly(messages=[{"role": "user", "content": "hi"}], config=config) is called
  Then  the returned string equals "Hello"

Scenario: call_provider_directly raises ConfigurationError for an unsupported provider
  Given SRFConfig with llm_provider="unsupported_provider"
  When  call_provider_directly(messages, config) is called
  Then  it raises ConfigurationError listing the supported providers

Scenario: call_provider_directly raises LLMError on provider 5xx response
  Given a mock provider SDK that raises an API error with status 500
  When  call_provider_directly(messages, config) is called
  Then  it raises LLMError containing the status code

Scenario: call_provider_directly does not import the non-configured provider SDK
  Given SRFConfig with llm_provider="anthropic"
  When  call_provider_directly(messages, config) is called
  Then  the openai module is not imported at the top level of fallback.py

Scenario: call_provider_directly integration test makes a real call (integration)
  Given SRF_LLM_PROVIDER, SRF_LLM_MODEL, and SRF_LLM_API_KEY are set
  When  call_provider_directly([{"role": "user", "content": "Reply with the word PONG only"}], config) is called
  Then  the returned string contains "PONG"
```

**TDD Notes:** Mock the provider SDK at the SDK call level (e.g., patch `anthropic.AsyncAnthropic`). The integration test is the only place a real provider SDK is called; skip with `pytest.mark.skipif` when `SRF_LLM_PROVIDER` is absent. Both provider SDK imports must be lazy (inside the function body) — the module must not fail to import when only one SDK is installed.

---

### Story 5.2 — Agent Roster

**As a** system,
**I would like** a roster function that takes a `ForumWorkspace` and `ExtractionResult` and produces an `AgentRoster` assigning agents to papers and roles,
**so that** the preparation phase knows exactly which agents exist, what they are assigned, and in what order they will participate.

**Files:**
- NEW: `src/srf/agents/__init__.py`
- NEW: `src/srf/agents/models.py`
- NEW: `src/srf/agents/roster.py`
- NEW: `tests/unit/test_agent_roster.py`

**Acceptance Criteria:**

```gherkin
Scenario: build_roster assigns one Paper Agent per successfully extracted paper
  Given an ExtractionResult with 3 papers having extraction_status "ok"
  When  build_roster(workspace, extraction_result) is called
  Then  the roster contains 3 Paper Agents
  And   each Paper Agent has a unique agent_id matching "paper-agent-{N}"
  And   each Paper Agent is assigned a distinct arxiv_id

Scenario: build_roster excludes papers with failed extraction from agent assignment
  Given an ExtractionResult with 2 ok papers and 1 failed paper
  When  build_roster(workspace, extraction_result) is called
  Then  the roster contains 2 Paper Agents
  And   no Paper Agent is assigned the failed paper's arxiv_id

Scenario: build_roster always includes exactly one Moderator and one Challenger
  Given any valid ExtractionResult with at least 2 ok papers
  When  build_roster(workspace, extraction_result) is called
  Then  the roster contains exactly one agent with role "moderator"
  And   the roster contains exactly one agent with role "challenger"

Scenario: build_roster raises RosterError when fewer than SRF_MIN_AGENTS papers are available
  Given an ExtractionResult where only 1 paper has extraction_status "ok"
  When  build_roster(workspace, extraction_result) is called
  Then  it raises RosterError with a message indicating insufficient papers

Scenario: AgentRoster serialises to and from JSON without data loss
  Given an AgentRoster with 2 Paper Agents, a Moderator, and a Challenger
  When  it is serialised to JSON and deserialised
  Then  the result equals the original roster

Scenario: build_roster writes roster.json to the workspace
  Given a valid ExtractionResult
  When  build_roster(workspace, extraction_result) is called
  Then  roster.json exists at workspace_path/roster.json
  And   it deserialises to the returned AgentRoster
```

**TDD Notes:** No LLM calls — pure domain logic. The `SRF_MIN_AGENTS` check should read from config or be injected as a parameter for testability. Agents are ordered: Paper Agents (1 to N) then Moderator then Challenger.

---

### Story 5.3 — Paper Agent Preparation

**As a** system,
**I would like** a preparation function that constructs a `PreparationArtifact` for a single Paper Agent via an LLM call,
**so that** each Paper Agent enters the debate with a declared position, key arguments, anticipated objections, and epistemic confidence grounded in their assigned paper.

**Files:**
- NEW: `src/srf/agents/preparation.py`
- NEW: `src/srf/prompts/agents.py`
- NEW: `tests/unit/test_paper_agent_preparation.py`
- MODIFY: `src/srf/prompts/__init__.py`

**Acceptance Criteria:**

```gherkin
Scenario: prepare_paper_agent returns a PreparationArtifact with all required fields
  Given a valid AgentAssignment for a Paper Agent
  And   a mock tracker whose execute coroutine returns a valid PreparationArtifact JSON as response_text
  When  prepare_paper_agent(assignment, paper_content, framing_question, tracker=mock_tracker, config=config, state={"trace_id": "t1"}) is called
  Then  result.agent_id equals assignment.agent_id
  And   result.claimed_position is a non-empty string
  And   result.key_arguments is a list of at least 2 non-empty strings
  And   result.anticipated_objections is a list of at least 1 non-empty string
  And   result.epistemic_confidence is a float between 0.0 and 1.0

Scenario: prepare_paper_agent injects paper text truncated to SRF_PAPER_TOKEN_BUDGET
  Given a PaperContent whose full_text exceeds SRF_PAPER_TOKEN_BUDGET characters
  And   a mock tracker whose execute coroutine captures the messages argument
  When  prepare_paper_agent(assignment, paper_content, framing_question, tracker=mock_tracker, config=config, state={}) is called
  Then  the messages argument passed to execute has user content of at most SRF_PAPER_TOKEN_BUDGET characters of paper text
  And   a WARNING is logged containing the arxiv_id and the number of characters truncated

Scenario: prepare_paper_agent injects an empty memory_block when no memory exists
  Given a mock tracker whose execute coroutine captures the messages argument
  When  prepare_paper_agent is called with memory_block=""
  Then  the system message in the captured messages contains the "{memory_block}" slot rendered as an empty string
  And   no error is raised

Scenario: prepare_paper_agent calls tracker.execute with the paper_preparation prompt name
  Given a mock tracker whose execute coroutine returns a valid ExecutionResult
  When  prepare_paper_agent(assignment, paper_content, framing_question, tracker=mock_tracker, config=config, state={"trace_id": "t1"}) is called
  Then  mock_tracker.execute was called once with prompt_name="agent.paper_preparation"
  And   it was called with agent_id=assignment.agent_id
  And   state["last_span_id"] is set to the span_id from the ExecutionResult

Scenario: prepare_paper_agent completes without error when tracker is None
  Given call_provider_directly returns a valid preparation JSON string
  When  prepare_paper_agent(assignment, paper_content, framing_question, tracker=None, config=config, state={}) is called
  Then  it returns a PreparationArtifact without raising
  And   no PromptLedger endpoint is called

Scenario: prepare_paper_agent raises PreparationError when LLM returns malformed JSON
  Given a mock tracker whose execute coroutine returns ExecutionResult with response_text="not-json"
  When  prepare_paper_agent(assignment, paper_content, framing_question, tracker=mock_tracker, config=config, state={}) is called
  Then  it raises PreparationError with a message indicating the parse failure

Scenario: paper_preparation prompt is registered and contains required slots
  Given the prompt registry in src/srf/prompts/agents.py
  When  the prompt named "agent.paper_preparation" is inspected
  Then  its template contains "{paper_text}", "{framing_question}", and "{memory_block}" slots
```

**TDD Notes:** Mock `tracker.execute` with `AsyncMock(return_value=ExecutionResult(response_text=json.dumps({...}), span_id="span-001", ...))`. The LLM is expected to return structured JSON matching the `PreparationArtifact` schema — test the parse step in isolation. Memory injection is a parameter `memory_block: str = ""` — the caller is responsible for providing it; this story always passes empty string. For `tracker=None` tests, patch `call_provider_directly`.

---

### Story 5.4 — Moderator Briefing & Challenger Preparation

**As a** system,
**I would like** preparation functions for the Moderator and Challenger that produce structured briefing documents via LLM calls,
**so that** the Moderator enters the debate with a structured agenda and the Challenger has declared a skeptical angle.

**Files:**
- MODIFY: `src/srf/agents/preparation.py`
- MODIFY: `src/srf/prompts/agents.py`
- NEW: `tests/unit/test_moderator_challenger_preparation.py`

**Acceptance Criteria:**

```gherkin
Scenario: prepare_moderator returns a ModeratorBriefing with debate_agenda and agent_profiles
  Given a valid AgentRoster
  And   a mock tracker whose execute coroutine returns a valid ModeratorBriefing JSON as response_text
  When  prepare_moderator(roster, framing_question, paper_summaries, tracker=mock_tracker, config=config, state={"trace_id": "t1"}) is called
  Then  result.debate_agenda is a list of at least 3 non-empty strings
  And   result.agent_profiles contains one entry per Paper Agent in the roster
  And   result.escalation_policy is a non-empty string

Scenario: prepare_moderator uses paper summaries not full text
  Given a mock tracker whose execute coroutine captures the messages argument
  When  prepare_moderator(roster, framing_question, paper_summaries, tracker=mock_tracker, config=config, state={}) is called
  Then  the messages argument user content contains each paper summary from paper_summaries
  And   the messages argument user content does not contain the string "full_text"

Scenario: prepare_moderator calls tracker.execute with the moderator_briefing prompt name
  Given a mock tracker whose execute coroutine returns a valid ExecutionResult
  When  prepare_moderator(roster, framing_question, paper_summaries, tracker=mock_tracker, config=config, state={"trace_id": "t1"}) is called
  Then  mock_tracker.execute was called once with prompt_name="agent.moderator_briefing"
  And   state["last_span_id"] is set to the span_id from the ExecutionResult

Scenario: prepare_challenger returns a ChallengerPreparation with skeptical_stance and challenge_angles
  Given a valid AgentRoster
  And   a mock tracker whose execute coroutine returns a valid ChallengerPreparation JSON as response_text
  When  prepare_challenger(roster, framing_question, paper_abstracts, tracker=mock_tracker, config=config, state={"trace_id": "t1"}) is called
  Then  result.skeptical_stance is a non-empty string
  And   result.challenge_angles is a list of at least 2 non-empty strings
  And   result.anticipated_defenses is a list of at least 1 non-empty string

Scenario: prepare_challenger calls tracker.execute with the challenger_preparation prompt name
  Given a mock tracker whose execute coroutine returns a valid ExecutionResult
  When  prepare_challenger(roster, framing_question, paper_abstracts, tracker=mock_tracker, config=config, state={"trace_id": "t1"}) is called
  Then  mock_tracker.execute was called once with prompt_name="agent.challenger_preparation"
  And   state["last_span_id"] is set to the span_id from the ExecutionResult

Scenario: moderator_briefing prompt contains required slots
  Given the prompt named "agent.moderator_briefing"
  When  its template is inspected
  Then  it contains "{framing_question}", "{paper_summaries}", "{agent_roster}", and "{memory_block}" slots

Scenario: challenger_preparation prompt contains required slots
  Given the prompt named "agent.challenger_preparation"
  When  its template is inspected
  Then  it contains "{framing_question}", "{paper_abstracts}", and "{memory_block}" slots
```

**TDD Notes:** Moderator receives `paper_summaries` (newsletter `technical_summary` fields — short). Challenger receives `paper_abstracts` (extracted abstract from `PaperContent.abstract` — medium length). Neither receives full paper text. Both use `memory_block=""` in this epic. Mock `tracker.execute` with `AsyncMock(return_value=ExecutionResult(...))` — never mock provider SDKs.

---

### Story 5.5 — Parallel Preparation Orchestration & CLI Script

**As a** system,
**I would like** an orchestration function that runs all agent preparations concurrently and a Lobster step script that invokes it,
**so that** preparation completes as fast as possible and the partial failure policy is enforced before the debate begins.

**Files:**
- NEW: `src/srf/agents/orchestrator.py`
- MODIFY: `scripts/run_preparation.py` _(new file — listed as MODIFY because srf_forum.yaml references it)_
- MODIFY: `workflows/srf_forum.yaml`
- NEW: `tests/unit/test_preparation_orchestrator.py`
- NEW: `tests/unit/test_run_preparation.py`
- NEW: `tests/integration/test_preparation_integration.py`

**Acceptance Criteria:**

```gherkin
Scenario: run_preparation executes all agent preparations concurrently
  Given an AgentRoster with 3 Paper Agents, a Moderator, and a Challenger
  And   mock prepare functions that record their start times
  When  run_preparation(roster, workspace, tracker=mock_tracker, config=config, state={"trace_id": "t1"}) is called
  Then  all preparation calls are initiated before any one of them returns
  And   the total duration is less than the sum of individual preparation durations

Scenario: run_preparation retries a failed Paper Agent preparation up to SRF_MAX_PREP_RETRIES times
  Given a mock prepare_paper_agent that fails twice then succeeds
  When  run_preparation is called with SRF_MAX_PREP_RETRIES=3
  Then  prepare_paper_agent was called 3 times for that agent
  And   the returned roster marks that agent as status "ok"

Scenario: run_preparation marks a Paper Agent as degraded after retries exhausted
  Given a mock prepare_paper_agent that always raises PreparationError
  And   the roster has 3 Paper Agents
  When  run_preparation is called with SRF_MAX_PREP_RETRIES=3
  Then  that agent's status in the result is "degraded"
  And   a WARNING is logged with the agent_id and final error

Scenario: run_preparation proceeds when degraded agents still meet SRF_MIN_AGENTS threshold
  Given 3 Paper Agents where 1 always fails and SRF_MIN_AGENTS=2
  When  run_preparation is called
  Then  it returns without raising
  And   the result contains 2 agents with status "ok" and 1 with status "degraded"

Scenario: run_preparation raises OrchestrationError when degraded agents drop below SRF_MIN_AGENTS
  Given 2 Paper Agents where both always fail and SRF_MIN_AGENTS=2
  When  run_preparation is called
  Then  it raises OrchestrationError with a message indicating insufficient agents

Scenario: run_preparation aborts if Moderator preparation fails after all retries
  Given a mock prepare_moderator that always raises PreparationError
  When  run_preparation is called
  Then  it raises OrchestrationError indicating Moderator preparation failed
  And   the error distinguishes Moderator failure from Paper Agent failure

Scenario: run_preparation writes all successful artifacts to workspace and updates state.json
  Given all mock preparations succeed
  When  run_preparation is called
  Then  artifact.json exists at workspace_path/preparation/{agent_id}/artifact.json for each agent
  And   state.json contains forum_status="preparation_complete"
  And   state.json contains a count of prepared agents

Scenario: run_preparation.py script exits 0 and writes preparation summary to stdout JSON
  Given valid stdin JSON from paper_extraction step and PROMPTLEDGER_API_URL configured
  When  scripts/run_preparation.py is run
  Then  it exits with code 0
  And   stdout JSON contains agent_count and preparation_status for each agent

Scenario: srf_forum.yaml agent_preparation step is wired to run_preparation.py
  Given the file workflows/srf_forum.yaml
  When  it is parsed as YAML
  Then  the step named "agent_preparation" uses run: python scripts/run_preparation.py
  And   it uses stdin: $paper_extraction.json
```

**TDD Notes:** Concurrent execution test: use `asyncio.gather` with mock coroutines that record `asyncio.get_event_loop().time()` at entry. The "all initiated before any returns" assertion checks that start times overlap (no sequential gap between last start and first finish). For the integration test, skip when `SRF_LLM_PROVIDER` is absent — it calls real provider APIs.

---

## Implementation Order

```
Story 5.1 (call_provider_directly fallback — establishes tracker=None path for all subsequent stories)
  → Story 5.2 (agent roster — depends on workspace + extraction models from Epic 4)
    → Story 5.3 (Paper Agent preparation — depends on 5.1 fallback + roster)
      → Story 5.4 (Moderator + Challenger preparation — depends on 5.3 prep infrastructure)
        → Story 5.5 (parallel orchestration — depends on 5.2, 5.3, 5.4)
```

All stories are sequential.

---

## Verification Checklist

```bash
# After 5.1
pytest tests/unit/test_llm_fallback.py -v

# After 5.2
pytest tests/unit/test_agent_roster.py -v

# After 5.3
pytest tests/unit/test_paper_agent_preparation.py -v
python -c "from srf.prompts.agents import AGENT_PROMPTS; print([p.name for p in AGENT_PROMPTS])"
# Expects: ['agent.paper_preparation']

# After 5.4
pytest tests/unit/test_moderator_challenger_preparation.py -v
python -c "from srf.prompts.agents import AGENT_PROMPTS; print([p.name for p in AGENT_PROMPTS])"
# Expects: ['agent.paper_preparation', 'agent.moderator_briefing', 'agent.challenger_preparation']

# After 5.5
pytest tests/unit/test_preparation_orchestrator.py tests/unit/test_run_preparation.py -v
python -c "import yaml; w = yaml.safe_load(open('workflows/srf_forum.yaml')); s = next(s for s in w['steps'] if s['name']=='agent_preparation'); print(s['run'])"
# Expects: python scripts/run_preparation.py

# Full epic suite
pytest tests/unit -v --tb=short
ruff check src/ tests/ scripts/

# With live LLM provider:
pytest tests/integration/test_llm_fallback_integration.py -v
pytest tests/integration/test_preparation_integration.py -v
```

---

## Critical Files

**NEW:**
- `src/srf/llm/__init__.py`
- `src/srf/llm/fallback.py`  _(call_provider_directly — tracker=None path only)_
- `src/srf/agents/__init__.py`
- `src/srf/agents/models.py`
- `src/srf/agents/roster.py`
- `src/srf/agents/preparation.py`
- `src/srf/agents/orchestrator.py`
- `src/srf/prompts/agents.py`
- `scripts/run_preparation.py`
- `tests/unit/test_llm_fallback.py`
- `tests/unit/test_agent_roster.py`
- `tests/unit/test_paper_agent_preparation.py`
- `tests/unit/test_moderator_challenger_preparation.py`
- `tests/unit/test_preparation_orchestrator.py`
- `tests/unit/test_run_preparation.py`
- `tests/integration/test_llm_fallback_integration.py`
- `tests/integration/test_preparation_integration.py`

**MODIFY:**
- `src/srf/prompts/__init__.py`
- `workflows/srf_forum.yaml` _(agent_preparation step wired)_
- `pyproject.toml` _(add `anthropic` and `openai` as optional dependencies)_
- `Requirements/progress.md`
