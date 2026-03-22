# Epic 11: PromptLedger Proxy — Turn-Level Telemetry for OpenClaw-Native Debate

## Prerequisites

- Epic 6B (Debate Engine — OpenClaw Native) — complete. The full OpenClaw skill session, bridge script, and debate workflow must be in production before this epic is scoped in detail. The proxy must be designed against the actual API surface OpenClaw exposes, not assumptions made before 6B ran.
- Epic 1 (Foundation) — complete. `SRFConfig`, `build_tracker`, and the `tracker=None` graceful degradation pattern are required.

---

## Context

In Epic 6B, the LLM calls for each debate turn are made directly by the OpenClaw runtime when it spawns subagents. Python never touches these calls. PromptLedger's Mode 2 (Code-Based Tracking) pattern — where SRF calls `tracker.execute()` — has no insertion point here. The bridge script captures phase-level spans (debate start, debate close) but every individual turn — which agent spoke, which prompt was used, how many tokens, what latency — is invisible to PromptLedger.

This matters for Epic 9 (Observability). Cost reporting, per-agent token budgets, and prompt performance tracking all depend on turn-level span data. Without it, Epic 9 is limited to coarse phase-level aggregates and cannot answer the questions that motivated building observability in the first place.

The solution is to sit a proxy between OpenClaw and the LLM provider. OpenClaw points its base URL at the proxy; the proxy forwards to Anthropic and creates PromptLedger spans for each call, tagged with the current forum's trace_id.

---

## What We Gain

| Gap (before) | After this epic |
|---|---|
| Per-turn LLM calls in the debate loop are invisible to PromptLedger | Every OpenClaw LLM call creates a `llm.generation` span in PromptLedger under the correct forum trace |
| Epic 9 observability is limited to phase-level spans | Token counts, latency, and model usage are available per agent per turn |
| No cost attribution below the forum level | Cost can be broken down by agent role, debate phase, and individual turn |
| PromptLedger trace hierarchy is incomplete | Full hierarchy: trace(forum_id) → phase span → turn spans (proxy-captured) → guardrail child spans (bridge-submitted) |

---

## Architecture Decisions

### Proxy mode, not skill-level span submission

Two options exist for capturing turn-level spans in an OpenClaw-native debate:

1. **Skill-level integration** — the skill document instructs the agent to call a Python span-submission script via the exec tool after each turn. This adds latency to every turn, requires disciplined skill authoring, and couples observability to skill document logic. Any future skill change risks breaking span attribution. Rejected.

2. **Proxy infrastructure** — a proxy sits between OpenClaw and the LLM provider. OpenClaw's base URL is pointed at the proxy; the proxy forwards calls and submits spans to PromptLedger. Observability is transparent to skill authors, adds negligible latency, and is decoupled from skill logic. Chosen.

### PromptLedger proxy mode vs. third-party interceptor

PromptLedger may expose a native OpenAI-compatible proxy endpoint. Story 11.1 determines whether this exists and what its contract is. If it does not, a lightweight OpenAI-compatible interceptor (e.g. LiteLLM proxy with a custom callback, or a minimal FastAPI app) sits in front of Anthropic and submits spans to PromptLedger's `/v1/spans` endpoint after each call. Story 11.1 resolves this choice before implementation begins.

### Forum trace_id injection via custom header

OpenClaw must include the current forum's `trace_id` in each LLM call so the proxy can parent the turn span under the correct forum trace. The mechanism (custom HTTP header, request metadata, or request body field) is determined by Story 11.1 based on what OpenClaw's routing configuration supports. The bridge script already writes `trace_id` to the debate state document — the skill session reads it from there.

### Graceful degradation: proxy is optional

When `PROMPTLEDGER_PROXY_URL` is absent, OpenClaw routes directly to Anthropic. The system debates without turn-level telemetry — exactly the current 6B behaviour. This preserves the `tracker=None` graceful degradation principle across the whole stack. The proxy is an observability enhancement, not a dependency for debate execution.

---

## Stories

---

### Story 11.1 — Proxy Mode Investigation & Contract Definition

**As a** developer,
**I would like** a documented contract for how LLM calls from OpenClaw will be intercepted and forwarded to PromptLedger,
**so that** Stories 11.2–11.4 are built against a known API surface rather than assumptions.

**Context:** This is a focused investigation story. It produces a short decision record (added to this epic as an Architecture Decisions update) and the configuration schema used by subsequent stories. No production code is written in this story — only tests that validate connectivity to the chosen proxy approach.

**Files:**
- NEW: `tests/integration/test_proxy_connectivity.py`
- MODIFY: `Requirements/srf_epic_11_promptledger_proxy.md` _(Architecture Decisions updated with findings)_

**Acceptance Criteria:**

```gherkin
Scenario: proxy endpoint responds to a minimal OpenAI-compatible chat completion request
  Given PROMPTLEDGER_PROXY_URL is set in the environment
  And   a valid PROMPTLEDGER_API_KEY is set
  When  an OpenAI-compatible POST /v1/chat/completions request is sent to PROMPTLEDGER_PROXY_URL
  Then  the response has status 200
  And   the response body contains a "choices" array

Scenario: proxy endpoint rejects requests without authentication
  Given PROMPTLEDGER_PROXY_URL is set
  When  a request is sent without the Authorization header
  Then  the response has status 401 or 403

Scenario: proxy creates a PromptLedger span for a forwarded call
  Given PROMPTLEDGER_PROXY_URL is set and a known trace_id is injected via the agreed header
  When  a chat completion request is sent through the proxy
  Then  a GET to PromptLedger /v1/spans?trace_id={trace_id} returns at least one span
  And   that span has kind equal to "llm.generation"

Scenario: proxy connectivity test is skipped when PROMPTLEDGER_PROXY_URL is absent
  Given PROMPTLEDGER_PROXY_URL is not set in the environment
  When  the test suite runs
  Then  the proxy connectivity tests are skipped with a clear reason message
```

**TDD Notes:** All scenarios require a live proxy and live PromptLedger instance. Mark the module with `pytestmark = pytest.mark.integration`. Use `pytest.importorskip` or a session-scoped fixture that skips when `PROMPTLEDGER_PROXY_URL` is absent. Do not mock the proxy in this story — the point is to validate the real contract.

---

### Story 11.2 — OpenClaw Proxy Routing Configuration

**As a** system,
**I would like** OpenClaw to route all LLM API calls through the PromptLedger proxy when `PROMPTLEDGER_PROXY_URL` is set,
**so that** every debate turn is intercepted and a span is created in PromptLedger without any changes to skill documents or agent prompts.

**Context:** OpenClaw's `openclaw.json` (or equivalent Railway env var overrides) supports configuring the LLM base URL. This story wires `PROMPTLEDGER_PROXY_URL` into that configuration with a Railway startup script that patches the config when the env var is present.

**Files:**
- NEW: `scripts/configure_proxy.py`
- MODIFY: `Requirements/Railway/openclaw.json` _(base URL field documented — not committed with live values)_
- NEW: `tests/unit/test_configure_proxy.py`

**Acceptance Criteria:**

```gherkin
Scenario: configure_proxy writes the proxy base URL into openclaw.json when PROMPTLEDGER_PROXY_URL is set
  Given PROMPTLEDGER_PROXY_URL="https://proxy.example.com/v1" is set
  And   a valid openclaw.json exists at OPENCLAW_STATE_DIR
  When  scripts/configure_proxy.py is run
  Then  the agents.defaults.model section of openclaw.json contains the proxy base URL
  And   the auth token for the proxy is written to the appropriate auth profile

Scenario: configure_proxy leaves openclaw.json unchanged when PROMPTLEDGER_PROXY_URL is absent
  Given PROMPTLEDGER_PROXY_URL is not set
  And   a valid openclaw.json exists
  When  scripts/configure_proxy.py is run
  Then  the file is identical to its state before the script ran
  And   the script exits with code 0

Scenario: configure_proxy exits non-zero when openclaw.json does not exist
  Given PROMPTLEDGER_PROXY_URL is set
  And   OPENCLAW_STATE_DIR points to a directory with no openclaw.json
  When  scripts/configure_proxy.py is run
  Then  it exits with a non-zero code
  And   stderr contains a message identifying the missing file

Scenario: configure_proxy is idempotent — running it twice produces the same result
  Given PROMPTLEDGER_PROXY_URL is set and openclaw.json exists
  When  scripts/configure_proxy.py is run twice
  Then  the resulting openclaw.json is identical after both runs
```

**TDD Notes:** Use `tmp_path` and a fixture that creates a minimal valid `openclaw.json` for unit tests. No network calls in unit tests. The script reads the JSON, patches it in memory, and writes it back atomically (write to a temp file, then rename). Test idempotency explicitly — it will be run on every Railway deploy.

---

### Story 11.3 — Forum Trace Attribution

**As a** system,
**I would like** every OpenClaw LLM call during a debate session to carry the current forum's `trace_id` as a header or metadata field,
**so that** the proxy can parent each turn span under the correct forum trace in PromptLedger and the full trace hierarchy is reconstructable.

**Context:** The bridge script writes `trace_id` to the debate state document at the start of the debate. The OpenClaw skill session reads this document at startup. This story defines how `trace_id` travels from the state document into each LLM call, and validates that proxy-captured spans appear under the correct forum trace.

**Files:**
- MODIFY: `skills/trigger_newsletter_forum/SKILL.md` _(trace_id injection instruction added)_
- MODIFY: `scripts/prepare_debate_context.py` _(emit trace_id in debate context document)_
- NEW: `tests/unit/test_trace_attribution.py`
- MODIFY: `tests/unit/test_debate_skill_documents.py`

**Acceptance Criteria:**

```gherkin
Scenario: prepare_debate_context includes trace_id in the output document
  Given a valid forum_id and a debate context input
  When  prepare_debate_context.py is run
  Then  the output JSON contains a "trace_id" field
  And   "trace_id" equals the forum_id (or a deterministic derivative of it)

Scenario: SKILL.md instructs the agent to set trace_id header on all LLM calls
  Given the file skills/trigger_newsletter_forum/SKILL.md
  When  its content is read
  Then  it contains an instruction to read trace_id from the debate context document
  And   it contains an instruction to include trace_id in the agreed proxy attribution header

Scenario: test_debate_skill_documents validates trace_id instruction is present
  Given the SKILL.md file
  When  the skill document validation test runs
  Then  it asserts the trace_id instruction is present
  And   it asserts the proxy header name matches the constant defined in configure_proxy.py
```

**TDD Notes:** The `trace_id` header name must be a shared constant (defined once, imported by both `configure_proxy.py` and validated by tests). Do not hardcode the header string in two places. The skill document validation test (`test_debate_skill_documents.py`) already exists from 6B.2 — extend it rather than creating a separate file.

---

### Story 11.4 — Railway Wiring & End-to-End Validation

**As a** system,
**I would like** the proxy configuration to be wired into the Railway startup sequence and validated end-to-end against a live debate run,
**so that** turn-level PromptLedger spans are present after a real forum debate and the full trace hierarchy is verified.

**Context:** `scripts/srf_init.py` runs on Railway startup. This story adds `configure_proxy.py` to that startup sequence and provides an integration test that runs a minimal debate and verifies the resulting PromptLedger trace contains the expected span hierarchy.

**Files:**
- MODIFY: `scripts/srf_init.py` _(invoke configure_proxy.py before first agent turn)_
- NEW: `tests/integration/test_proxy_trace_hierarchy.py`

**Acceptance Criteria:**

```gherkin
Scenario: srf_init.py invokes configure_proxy.py before prompt registration
  Given srf_init.py is read
  When  its import and call order is inspected
  Then  configure_proxy is called before register_code_prompts

Scenario: after a live debate run proxy spans appear under the forum trace
  Given PROMPTLEDGER_PROXY_URL, PROMPTLEDGER_API_KEY, and SRF_LLM_API_KEY are set
  And   a minimal forum config with 2 papers and max_total_turns=2 is prepared
  When  the full debate workflow runs end-to-end
  Then  a GET to PromptLedger /v1/traces/{forum_id}/spans returns at least 2 spans with kind "llm.generation"
  And   each span has agent_id set to a known debate agent role
  And   the phase-level span from the bridge script is present with kind "workflow.phase"

Scenario: debate runs successfully when PROMPTLEDGER_PROXY_URL is absent
  Given PROMPTLEDGER_PROXY_URL is not set
  And   all other required env vars are set
  When  the full debate workflow runs end-to-end
  Then  the debate completes and the transcript is written
  And   no error is raised due to missing proxy configuration
```

**TDD Notes:** The live debate integration test is expensive — mark with `@pytest.mark.integration` and skip by default in CI. Run it manually or in a dedicated integration job. The `srf_init.py` call-order test is a unit test: parse the file with `ast` or read it line by line and assert `configure_proxy` appears before `register_code_prompts`. No live network required.

---

## Implementation Order

```
Story 11.1 (investigation — must run first; findings drive all subsequent stories)
  → Story 11.2 (proxy routing config — depends on 11.1 contract)
  → Story 11.3 (trace attribution — depends on 11.1 header contract)
    → Story 11.4 (Railway wiring + e2e — depends on 11.2 and 11.3)
```

Stories 11.2 and 11.3 can be developed in parallel once 11.1 is complete.

---

## Verification Checklist

```bash
# After 11.1 — integration only, requires live proxy
pytest tests/integration/test_proxy_connectivity.py -v

# After 11.2
pytest tests/unit/test_configure_proxy.py -v
python scripts/configure_proxy.py  # with PROMPTLEDGER_PROXY_URL set — verify openclaw.json updated

# After 11.3
pytest tests/unit/test_trace_attribution.py -v
pytest tests/unit/test_debate_skill_documents.py -v  # includes new trace_id assertion

# After 11.4
pytest tests/unit -v --tb=short     # full unit suite must stay GREEN
ruff check src/ tests/ scripts/
# Integration (requires live env):
pytest tests/integration/test_proxy_trace_hierarchy.py -v
```

---

## Critical Files

**NEW:**
- `scripts/configure_proxy.py`
- `tests/unit/test_configure_proxy.py`
- `tests/unit/test_trace_attribution.py`
- `tests/integration/test_proxy_connectivity.py`
- `tests/integration/test_proxy_trace_hierarchy.py`

**MODIFY:**
- `scripts/srf_init.py`
- `scripts/prepare_debate_context.py`
- `skills/trigger_newsletter_forum/SKILL.md`
- `tests/unit/test_debate_skill_documents.py`
- `Requirements/srf_epic_11_promptledger_proxy.md` _(Architecture Decisions updated after Story 11.1)_
