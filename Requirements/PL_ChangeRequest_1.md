# PromptLedger Change Request — CR-001
## Unified Execution Client: Pre-Rendered Message Support & Mode-Agnostic `execute()`

**Submitted by:** Synthetic Research Forum Team
**Date:** 2026-03-17
**Priority:** High — blocks Epic 5 implementation
**Target version:** `promptledger-client` SDK + `/v1/executions:run` API endpoint

---

## 1. Summary

Extend `POST /v1/executions:run` to accept pre-rendered `messages` arrays in addition to `prompt_name + variables`, and add an `AsyncPromptLedgerClient.execute()` SDK method that provides a unified, mode-agnostic interface for all LLM calls. This collapses the Mode 1 / Mode 2 execution distinction to a single axis — **where the prompt is managed** — while routing all LLM calls through PromptLedger for automatic span logging, cost tracking, and provider credential governance.

---

## 2. Problem Statement

### 2.1 The current Mode 2 boilerplate burden

Mode 2 integrations require ~20 lines of boilerplate per call site:

```python
# Current Mode 2 — every call site looks like this
import anthropic
import time
from datetime import datetime, timezone
from promptledger_client.models import SpanPayload

client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
start = time.time()
start_time = datetime.now(timezone.utc)

response = await client.messages.create(
    model=os.environ["SRF_LLM_MODEL"],
    max_tokens=1024,
    messages=[{"role": "user", "content": rendered_prompt}],
)

duration_ms = int((time.time() - start) * 1000)

if tracker is not None:
    await tracker.log_span(SpanPayload(
        trace_id=state["trace_id"],
        parent_span_id=state.get("phase_span_id"),
        name="agent.paper_preparation",
        kind="llm.generation",
        start_time=start_time.isoformat(),
        duration_ms=duration_ms,
        status="ok",
        model=os.environ["SRF_LLM_MODEL"],
        prompt_tokens=response.usage.input_tokens,
        completion_tokens=response.usage.output_tokens,
        prompt_name="agent.paper_preparation",
    ))

result = response.content[0].text
```

Every project using Mode 2 reimplements this pattern. Provider adapters are duplicated across codebases. There is no central credential governance.

### 2.2 The conceptual gap between modes

The integration guide describes Mode 1 and Mode 2 as fundamentally different execution models. This overstates the difference. The real distinction is only:

| Dimension | Mode 1 | Mode 2 |
|---|---|---|
| Prompt template lives in | PL database | App code (Git) |
| Prompt rendering | PL fills variables | App constructs messages |
| LLM execution | PL calls provider | **App calls provider** ← unnecessary |
| Span logging | Automatic | **Manual, ~20 lines** ← unnecessary |

After rendering, both modes do the same thing: call a provider and log a span. There is no reason for Mode 2 to duplicate this execution path in every project.

### 2.3 No cross-project provider governance

Each Mode 2 project holds its own provider API keys, chooses its own models, and has no centralised access control. There is no mechanism for an operator to:
- Restrict which models a given project may call
- Rotate provider credentials without redeploying every project
- View per-project cost across providers in one place

---

## 3. Proposed Solution

### 3.1 Conceptual model after this change

**Mode 1 and Mode 2 differ only in where the prompt is managed and constructed. Execution is identical.**

```
Mode 1:  [prompt in PL DB]  →  PL renders  →  PL calls provider  →  PL logs span  →  result
Mode 2:  [prompt in code]   →  app renders  →  PL calls provider  →  PL logs span  →  result
```

The app still registers its prompts with PL (for governance and drift detection). It constructs the final messages locally. It hands the rendered messages to PL for execution. PL logs the span automatically — no separate `POST /v1/spans` call required.

### 3.2 API change — `POST /v1/executions:run`

Add support for a `messages` array input alongside the existing `prompt_name + variables` path.

#### New request schema

```json
{
  "prompt_name": "agent.paper_preparation",
  "model": {
    "provider": "anthropic",
    "model_name": "claude-sonnet-4-6"
  },
  "params": {
    "max_new_tokens": 1024,
    "temperature": 0.7
  },

  "variables": {"paper_text": "...", "framing_question": "..."},

  "messages": [
    {"role": "system", "content": "You are a research agent..."},
    {"role": "user",   "content": "Full debate transcript + paper text..."}
  ],

  "mode": "mode2",

  "span": {
    "trace_id": "trace-abc123",
    "parent_span_id": "span-phase-001",
    "agent_id": "paper-agent-1",
    "kind": "llm.generation"
  }
}
```

#### Field rules

| Field | Mode 1 | Mode 2 |
|---|---|---|
| `prompt_name` | Required | Required (for span labelling + governance) |
| `variables` | Required | Optional — used if `messages` absent |
| `messages` | Not allowed | Optional — takes precedence over template rendering |
| `model` | Required | Optional if model is configured on PL for this project (Phase 2) |
| `mode` | `"mode1"` or omit | `"mode2"` |
| `span` | Auto-populated by PL | Caller provides `trace_id`, optional `parent_span_id` and `agent_id` |

**Validation rules:**
- If `mode="mode2"` and neither `variables` nor `messages` is provided → `400 Bad Request`
- If `mode="mode2"` and both `variables` and `messages` are provided → `messages` takes precedence; `variables` ignored
- If `mode="mode1"` and `messages` is provided → `400 Bad Request` (Mode 1 always renders from template)
- `prompt_name` is always required — it links the execution to the registered prompt for governance tracking

#### Response schema (unchanged)

```json
{
  "execution_id": "<uuid>",
  "status": "succeeded",
  "mode": "mode2",
  "response_text": "...",
  "span_id": "<uuid>",
  "telemetry": {
    "prompt_tokens": 4821,
    "response_tokens": 312,
    "latency_ms": 1840,
    "model_name": "claude-sonnet-4-6",
    "provider": "anthropic",
    "total_cost": 0.0058
  }
}
```

`span_id` is new — the ID of the span PL automatically created for this execution. Callers can store it in their workflow state for child span parenting without a separate `POST /v1/spans` call.

### 3.3 SDK change — `AsyncPromptLedgerClient.execute()`

```python
result = await tracker.execute(
    prompt_name="agent.paper_preparation",
    variables={"paper_text": "...", "framing_question": "...", "memory_block": ""},
    mode="mode2",
    state=state,          # optional — reads trace_id/parent_span_id, writes span_id back
    agent_id="paper-agent-1",
    max_tokens=1024,
    temperature=0.7,
)

# result.response_text: str
# result.span_id: str
# result.telemetry.prompt_tokens: int
# result.telemetry.completion_tokens: int
# result.telemetry.latency_ms: int
# result.telemetry.total_cost: float | None
```

For dynamic message construction (debate loops, transcript injection):

```python
result = await tracker.execute(
    prompt_name="agent.debate_turn",     # for governance — not used for rendering
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": current_transcript + framing_question},
    ],
    mode="mode2",
    state=state,
    agent_id="moderator",
)
```

#### `state` parameter behaviour

If `state` is provided:
- `state["trace_id"]` is read and passed as `span.trace_id`
- `state["phase_span_id"]` is read and passed as `span.parent_span_id` (if present)
- `result.span_id` is written back to `state["last_span_id"]` after execution

This eliminates manual span ID threading at every call site.

#### Mode 1 via `execute()`

```python
result = await tracker.execute(
    prompt_name="doc_summarizer",
    variables={"text": "..."},
    mode="mode1",          # PL renders template + executes
)
```

Identical interface. The only difference is PL renders the template rather than using the provided `messages`.

#### `tracker=None` behaviour

When `tracker` is `None`, `execute()` is unavailable. Call sites guard with `if tracker is not None` as today. A `NullExecutionClient` helper (see Section 3.4) handles the case where observability is optional but execution must still proceed.

### 3.4 `NullExecutionClient` for graceful degradation

For projects where PromptLedger is optional (observability disabled) but execution must still work, provide a `NullExecutionClient` that calls the provider directly without logging:

```python
from promptledger_client import AsyncPromptLedgerClient, NullExecutionClient

# At startup:
if promptledger_configured:
    client = AsyncPromptLedgerClient(base_url=..., api_key=...)
else:
    client = NullExecutionClient(
        provider=os.environ["SRF_LLM_PROVIDER"],
        model=os.environ["SRF_LLM_MODEL"],
        api_key=os.environ["SRF_LLM_API_KEY"],
    )

# At every call site — identical interface regardless:
result = await client.execute(
    prompt_name="agent.paper_preparation",
    messages=[...],
    mode="mode2",
)
```

`NullExecutionClient` implements the same `execute()` interface, calls the provider directly, returns the same `ExecutionResult` shape, and never calls any PromptLedger endpoint. This replaces the pattern of building per-project provider adapters (e.g., `AnthropicClient`, `OpenAIClient` in `src/srf/llm/`).

---

## 4. Phase 2 — API Gateway (Credential Governance)

This is a follow-on capability that becomes natural once Phase 1 is in place. Since PL is already executing all LLM calls, it can own provider credentials centrally.

### What changes

- PromptLedger holds provider API keys, scoped to projects
- Projects authenticate to PL only — no `SRF_LLM_API_KEY` in project config
- PL enforces which models each project is permitted to call
- `NullExecutionClient` is still available for fully offline/local operation

### New project config (Phase 2)

```env
# Phase 1 (current proposal)
PROMPTLEDGER_API_URL=https://pl.example.com
PROMPTLEDGER_API_KEY=pl-project-key
SRF_LLM_PROVIDER=anthropic
SRF_LLM_MODEL=claude-sonnet-4-6
SRF_LLM_API_KEY=sk-ant-...    # project holds its own key

# Phase 2 (API Gateway)
PROMPTLEDGER_API_URL=https://pl.example.com
PROMPTLEDGER_API_KEY=pl-project-key
# No provider key — PL gateway controls model access
```

### Operator capabilities (Phase 2)

| Capability | How |
|---|---|
| Restrict project to specific models | Per-project allowed model list in PL admin |
| Rotate provider credentials | Once in PL — no project redeployments |
| Per-project cost dashboard | Already available from execution telemetry |
| Block a project from production models | Remove from allowed list in PL admin |

Phase 2 is **fully backwards compatible** — projects with local provider keys continue to work. PL gateway is an opt-in configuration.

---

## 5. Impact on Integration Guide

Section 5 ("End-to-End Mode 2 Walkthrough") should be updated to show the new `execute()` pattern. The 20-line boilerplate example becomes:

```python
async def prepare_paper_agent(
    paper_text: str,
    framing_question: str,
    client,          # AsyncPromptLedgerClient or NullExecutionClient
    state: dict,
) -> str:
    result = await client.execute(
        prompt_name="agent.paper_preparation",
        messages=[
            {"role": "system", "content": PAPER_PREPARATION_SYSTEM_PROMPT},
            {"role": "user",   "content": f"{paper_text}\n\nFraming: {framing_question}"},
        ],
        mode="mode2",
        state=state,
        agent_id="paper-agent-1",
    )
    return result.response_text
```

The `tracker=None` test isolation pattern is replaced by the `NullExecutionClient` pattern — no network calls, same interface.

The Mode 1 vs Mode 2 decision guide should be updated to reflect that the distinction is now purely about **prompt management**, not execution complexity:

| Choose Mode 1 when | Choose Mode 2 when |
|---|---|
| Non-engineers need to edit prompts without a code deploy | Prompts are code — PR review required for changes |
| You want A/B testing or canary prompt versions | You want unit-testable prompts with `NullExecutionClient` |
| Prompt variables fully describe the call | Dynamic message construction needed (e.g. transcript injection) |

---

## 6. What This Change Eliminates for Downstream Projects

For any project using Mode 2 today (including SRF):

| Eliminated | Replaced by |
|---|---|
| Per-project provider adapter classes (`AnthropicClient`, `OpenAIClient`) | `AsyncPromptLedgerClient.execute()` or `NullExecutionClient` |
| Provider SDK imports in application code | None — SDK lives in `promptledger-client` only |
| Manual `SpanPayload` construction at every call site | Automatic — PL logs the span as part of execution |
| Separate `POST /v1/spans` call after each LLM call | Eliminated — span created during execution |
| `SRF_LLM_PROVIDER` / `SRF_LLM_API_KEY` (Phase 2) | `PROMPTLEDGER_API_KEY` only |
| ~20 lines of boilerplate per call site | 3–5 lines |

---

## 7. Backwards Compatibility

- All existing `POST /v1/executions:run` calls (Mode 1, `prompt_name + variables`) are unchanged
- All existing `POST /v1/spans` calls (current Mode 2) continue to work
- `register_code_prompts()` and `log_span()` on `AsyncPromptLedgerClient` are unchanged
- `execute()` is an additive method — no existing code breaks
- `NullExecutionClient` is a new class — no naming conflicts

---

## 8. Requested Deliverables

| # | Deliverable | Notes |
|---|---|---|
| 1 | `POST /v1/executions:run` accepts `messages` array | Server-side change |
| 2 | `POST /v1/executions:run` returns `span_id` in response | Server-side change |
| 3 | `AsyncPromptLedgerClient.execute()` method | SDK change |
| 4 | `NullExecutionClient` class | SDK change |
| 5 | `ExecutionResult` dataclass | SDK change |
| 6 | Updated integration guide (Sections 4–5) | Docs change |
| 7 | Phase 2 API Gateway design doc | Separate follow-on |

---

## 9. Open Questions for PromptLedger Team

1. **Async execution for Mode 2 `messages`**: Should `POST /v1/executions:submit` (async queue) also accept `messages`? SRF's preparation phase runs agents concurrently — if PL queues the calls, does that help or add latency?

2. **`prompt_name` requirement when using `messages`**: We've required `prompt_name` for governance even when `messages` is provided. Is there a preference for making it optional (anonymous execution) or keeping it required?

3. **Span `kind` defaulting**: When `execute()` is called without an explicit `kind`, should PL default to `llm.generation`? Or should the caller always specify?

4. **Phase 2 timeline**: Is credential governance (Phase 2) something the team wants to design now alongside Phase 1, or strictly sequenced after?
