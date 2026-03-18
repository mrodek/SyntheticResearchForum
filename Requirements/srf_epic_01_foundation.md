# Epic 1: Foundation — Project Scaffold, Configuration & PromptLedger Integration

## Prerequisites

None — this epic is self-contained. All subsequent epics depend on it.

---

## Context

No production code exists yet. Before any agent, workflow phase, or debate logic can be built, the project needs a reproducible package structure, a validated environment configuration layer, structured logging, and the PromptLedger Mode 2 observability foundation that every LLM call site will depend on. Without this scaffold, each subsequent epic would be inventing conventions independently and producing untraceable, untestable code.

---

## What We Gain

| Gap (before) | After this epic |
|---|---|
| No project structure — nowhere to put code | `src/srf/` package with consistent module layout |
| No dependency management | `pyproject.toml` with pinned deps; `ruff` enforced from day one |
| No environment validation | Config module raises at startup if required vars are absent |
| No logging — bare `print()` or nothing | Structured JSON log lines via `structlog`; component and forum_id bound per context |
| No PromptLedger integration | `tracker` available everywhere; graceful no-op when `PROMPTLEDGER_API_URL` is absent |
| LLM calls invisible to observability | Every LLM call wrapped with a `SpanPayload` regardless of provider; trace/phase/turn hierarchy established |
| Prompt drift undetectable in CI | `scripts/validate_prompts.py` dry-run blocks unregistered changes before merge |
| No test infrastructure | `pytest` + `pytest-asyncio` running; unit and integration suites separated |

---

## Architecture Decisions

### Provider-agnostic LLM configuration — HARD REQUIREMENT

SRF must not be coupled to any single LLM provider. The active provider, model, and API key are runtime configuration, not code. This is enforced at the config layer: `SRF_LLM_PROVIDER`, `SRF_LLM_MODEL`, and `SRF_LLM_API_KEY` are the only LLM-related required vars. No provider SDK is imported unconditionally — provider clients are instantiated at startup based on `SRF_LLM_PROVIDER`. Adding a new provider must require no changes outside `src/srf/llm/`.

### PromptLedger Mode 2, not Mode 1

SRF calls the configured LLM provider directly and logs spans to PromptLedger after the fact. Mode 1 (PromptLedger executes the LLM call) is not used because SRF requires full control of message construction, system prompts, and streaming — none of which Mode 1 supports cleanly. PromptLedger is observability infrastructure, not an execution proxy.

### `tracker=None` injection over module-level singleton

Every function that calls PromptLedger accepts `tracker: AsyncPromptLedgerClient | None` as a parameter. The singleton-in-`observability.py` is only used as the call-site default. This makes unit testing trivially free of network calls and keeps the dependency explicit.

### Span IDs through workflow state, not `contextvars`

SRF runs on Railway with sleep/wake cycles. Workflow phases execute in separate invocations. `contextvars` do not survive across invocations. All `trace_id` and `parent_span_id` values are stored in the workflow state dict and passed explicitly. `contextvars` are only used within a single in-process async turn for trace ID propagation.

### `structlog` over stdlib `logging`

`structlog` produces JSON-lines natively, binds context (forum_id, phase, agent_id) per coroutine without thread-local footguns, and integrates with stdlib for third-party library output. All log calls use `structlog`; `print()` is banned in production paths.

---

## Stories

---

### Story 1.1 — Project Scaffold

**As a** developer,
**I would like** a fully configured Python package with dependency management, linting, and test infrastructure,
**so that** every subsequent story starts from a consistent, reproducible baseline.

**Files:**
- NEW: `pyproject.toml`
- NEW: `src/srf/__init__.py`
- NEW: `src/srf/py.typed`
- NEW: `tests/__init__.py`
- NEW: `tests/unit/__init__.py`
- NEW: `tests/integration/__init__.py`
- NEW: `tests/fixtures/__init__.py`
- NEW: `tests/fixtures/conftest.py`
- NEW: `.env.example`
- NEW: `.gitignore`
- NEW: `Makefile`

**Acceptance Criteria:**

```gherkin
Scenario: package is importable
  Given the package is installed with `pip install -e .`
  When  `import srf` is executed
  Then  no ImportError is raised

Scenario: ruff passes on the initial scaffold
  Given the scaffold files exist
  When  `ruff check src/ tests/` is run
  Then  it exits with code 0

Scenario: pytest discovers tests on a clean install
  Given the package is installed
  When  `pytest tests/unit -v` is run
  Then  it exits with code 0 (no tests collected is acceptable at this stage)

Scenario: .env.example documents all required variables
  Given `.env.example` exists
  When  it is read
  Then  it contains SRF_LLM_PROVIDER, SRF_LLM_MODEL, SRF_LLM_API_KEY,
        PROMPTLEDGER_API_URL, PROMPTLEDGER_API_KEY, SRF_WORKSPACE_ROOT,
        and SRF_LOG_LEVEL entries with placeholder values
```

**TDD Notes:** The "no tests collected" exit code 0 is acceptable for Story 1.1 only. From Story 1.2 onward, every story must have at least one test that goes RED before GREEN.

---

### Story 1.2 — Configuration Module

**As a** system,
**I would like** a configuration module that validates environment variables at startup,
**so that** missing required config fails loudly at boot rather than silently at runtime.

**Files:**
- NEW: `src/srf/config.py`
- NEW: `tests/unit/test_config.py`

**Acceptance Criteria:**

```gherkin
Scenario: config loads successfully when all required vars are set
  Given SRF_LLM_PROVIDER, SRF_LLM_MODEL, SRF_LLM_API_KEY, SRF_WORKSPACE_ROOT,
        and SRF_LOG_LEVEL are set in the environment
  When  SRFConfig.from_env() is called
  Then  it returns a config object with all fields populated

Scenario: config raises on missing SRF_LLM_PROVIDER
  Given SRF_LLM_PROVIDER is absent from the environment
  When  SRFConfig.from_env() is called
  Then  it raises ConfigurationError with a message naming the missing variable

Scenario: config raises on missing SRF_LLM_API_KEY
  Given SRF_LLM_API_KEY is absent from the environment
  When  SRFConfig.from_env() is called
  Then  it raises ConfigurationError with a message naming the missing variable

Scenario: config raises on missing SRF_LLM_MODEL
  Given SRF_LLM_MODEL is absent from the environment
  When  SRFConfig.from_env() is called
  Then  it raises ConfigurationError with a message naming the missing variable

Scenario: config raises on unrecognised SRF_LLM_PROVIDER value
  Given SRF_LLM_PROVIDER is set to "unknown_provider"
  When  SRFConfig.from_env() is called
  Then  it raises ConfigurationError listing the supported provider values

Scenario: PromptLedger config is optional
  Given PROMPTLEDGER_API_URL and PROMPTLEDGER_API_KEY are absent
  When  SRFConfig.from_env() is called
  Then  it returns a config with promptledger_enabled = False and no error raised

Scenario: PromptLedger requires both vars or neither
  Given PROMPTLEDGER_API_URL is set but PROMPTLEDGER_API_KEY is absent
  When  SRFConfig.from_env() is called
  Then  it raises ConfigurationError indicating that both vars must be set together

Scenario: SRF_LOG_LEVEL defaults to INFO when absent
  Given SRF_LOG_LEVEL is not set
  When  SRFConfig.from_env() is called
  Then  config.log_level equals "INFO"

Scenario: SRF_WORKSPACE_ROOT defaults when absent
  Given SRF_WORKSPACE_ROOT is not set
  When  SRFConfig.from_env() is called
  Then  config.workspace_root equals Path("/data/workspace")
```

---

### Story 1.3 — Structured Logging

**As a** developer,
**I would like** structured JSON logging via `structlog` with per-context binding,
**so that** every log line is machine-parseable and carries forum_id, phase, and component context without manual threading.

**Files:**
- NEW: `src/srf/logging.py`
- NEW: `tests/unit/test_logging.py`

**Acceptance Criteria:**

```gherkin
Scenario: configure_logging produces JSON output at the configured level
  Given SRF_LOG_LEVEL is set to "WARNING"
  When  configure_logging() is called and a WARNING event is logged
  Then  the output is a valid JSON object containing "level", "event", and "timestamp" keys

Scenario: DEBUG events are suppressed when log level is INFO
  Given SRF_LOG_LEVEL is set to "INFO"
  When  configure_logging() is called and a DEBUG event is logged
  Then  nothing is written to the output stream

Scenario: get_logger returns a logger bound with component name
  Given configure_logging() has been called
  When  get_logger("lobster.phase") is called and an event is logged
  Then  the log output contains "component": "lobster.phase"

Scenario: bind_context attaches forum_id to all subsequent log calls in the same coroutine
  Given a logger obtained via get_logger()
  When  bind_context(forum_id="forum-abc") is called then an event is logged
  Then  the log output contains "forum_id": "forum-abc"

Scenario: no print() calls reach production log paths
  Given the srf package source files
  When  they are scanned for bare print() calls
  Then  none are found outside of test files and scripts
```

**TDD Notes:** Use `structlog.testing.capture_logs()` for the unit tests — no real I/O needed. The `print()` scan scenario is implemented as a `pytest` test that greps `src/srf/` with `ast.parse`.

---

### Story 1.4 — PromptLedger Observability Module

**As a** system,
**I would like** an observability module that provides an `AsyncPromptLedgerClient` when PromptLedger is configured and `None` otherwise,
**so that** every call site can use `if tracker is not None:` without worrying about SDK availability.

**Files:**
- NEW: `src/srf/observability.py`
- NEW: `tests/unit/test_observability.py`
- NEW: `tests/integration/test_observability_integration.py`

**Acceptance Criteria:**

```gherkin
Scenario: tracker is None when PROMPTLEDGER_API_URL is absent
  Given PROMPTLEDGER_API_URL is not set
  When  build_tracker(config) is called
  Then  it returns None without raising

Scenario: tracker is an AsyncPromptLedgerClient when both PL vars are set
  Given PROMPTLEDGER_API_URL and PROMPTLEDGER_API_KEY are set
  When  build_tracker(config) is called
  Then  it returns an instance of AsyncPromptLedgerClient

Scenario: build_tracker logs a warning and returns None if the SDK import fails
  Given promptledger_client is not installed
  When  build_tracker(config) is called
  Then  it returns None and logs a WARNING containing "observability disabled"

Scenario: register_prompts is a no-op when tracker is None
  Given tracker is None
  When  register_prompts(tracker, prompts=[...]) is called
  Then  it returns without error and makes no network calls

Scenario: register_prompts calls register_code_prompts when tracker is provided (integration)
  Given a live PromptLedger instance and a valid tracker
  When  register_prompts(tracker, prompts=[RegistrationPayload(...)]) is called
  Then  the response indicates at least one prompt was registered or unchanged
```

**TDD Notes:** The integration test requires `PROMPTLEDGER_API_URL` and `PROMPTLEDGER_API_KEY` in the environment; skip it with `pytest.mark.skipif` when absent.

---

### Story 1.5 — Span Logging Utilities

**As a** system,
**I would like** utility functions for building and submitting `SpanPayload` objects with correct trace/phase/turn hierarchy,
**so that** individual agent functions don't each re-implement span construction logic.

**Files:**
- NEW: `src/srf/spans.py`
- NEW: `tests/unit/test_spans.py`

**Acceptance Criteria:**

```gherkin
Scenario: log_span returns None when tracker is None
  Given tracker is None
  When  log_span(tracker=None, state={}, name="test", kind="llm.generation", status="ok") is called
  Then  it returns None without raising

Scenario: log_span submits a SpanPayload and returns a span_id string when tracker is provided
  Given a mock tracker whose log_span coroutine returns "span-xyz"
  When  log_span(tracker=mock_tracker, state={"trace_id": "t1"}, name="test", kind="llm.generation", status="ok") is called
  Then  it returns "span-xyz"

Scenario: log_span reads trace_id from state dict
  Given state = {"trace_id": "trace-abc", "phase_span_id": "span-parent"}
  When  log_span is called with that state
  Then  the submitted SpanPayload has trace_id="trace-abc" and parent_span_id="span-parent"

Scenario: log_span stores the returned span_id back into state under the given state_key
  Given state = {"trace_id": "t1"} and state_key = "phase_span_id"
  When  log_span is called with state_key="phase_span_id"
  Then  state["phase_span_id"] equals the returned span_id

Scenario: build_llm_span_payload includes token and cost fields from a provider usage object
  Given a usage object with input_tokens=200 and output_tokens=80
  When  build_llm_span_payload(name=..., usage=usage_obj, duration_ms=500, ...) is called
  Then  the SpanPayload has prompt_tokens=200 and completion_tokens=80

Scenario: log_span is a no-op and does not raise when PromptLedger returns a 5xx error
  Given a mock tracker whose log_span coroutine raises an httpx.HTTPStatusError(status=503)
  When  log_span is called
  Then  it returns None without propagating the exception
```

**TDD Notes:** All unit tests use a mock tracker — no live PromptLedger needed. The 5xx resilience test verifies that observability failures never interrupt the debate workflow.

---

### Story 1.6 — CI Prompt Validation Script

**As a** developer,
**I would like** a CI script that dry-runs prompt registration against PromptLedger and fails if any prompt template has changed without being registered,
**so that** untracked prompt changes cannot reach `main`.

**Files:**
- NEW: `scripts/validate_prompts.py`
- NEW: `src/srf/prompts/__init__.py`
- NEW: `tests/unit/test_validate_prompts.py`

**Acceptance Criteria:**

```gherkin
Scenario: script exits 0 when all prompts are in sync
  Given a mock PromptLedger endpoint that returns all prompts as "unchanged"
  When  validate_prompts.py is run
  Then  it exits with code 0 and prints an OK summary

Scenario: script exits 1 when any prompt has an unregistered change
  Given a mock PromptLedger endpoint that returns one prompt as "update"
  When  validate_prompts.py is run
  Then  it exits with code 1 and prints the name of the changed prompt

Scenario: script exits 1 when a prompt exists in code but is absent from PromptLedger
  Given a mock endpoint that returns one prompt as "new"
  When  validate_prompts.py is run
  Then  it exits with code 1

Scenario: script exits 0 with a clear skip message when PROMPTLEDGER_API_URL is absent
  Given PROMPTLEDGER_API_URL is not set in the environment
  When  validate_prompts.py is run
  Then  it exits with code 0 and prints "SKIP: PromptLedger not configured"

Scenario: template_hash in the payload is the SHA-256 of the template source
  Given a prompt template string "You are a researcher..."
  When  checksum() is called on that string
  Then  it returns the expected 64-character hex digest
```

**TDD Notes:** Mock the `httpx.AsyncClient` for unit tests so no live PromptLedger is needed. The skip-when-absent scenario is critical — CI must not fail in environments without PromptLedger configured.

---

## Implementation Order

```
Story 1.1 (scaffold)
  → Story 1.2 (config)
    → Story 1.3 (logging)        parallel with →  Story 1.4 (observability)
      → Story 1.5 (spans)
        → Story 1.6 (CI validation)
```

Stories 1.3 and 1.4 can be developed in parallel once 1.2 is complete, as they have no mutual dependency. Story 1.5 requires both 1.3 (for warning logs on span errors) and 1.4 (for the tracker type).

---

## Verification Checklist

```bash
# After 1.1
pip install -e ".[dev]"
ruff check src/ tests/
pytest tests/unit -v

# After 1.2
pytest tests/unit/test_config.py -v

# After 1.3
pytest tests/unit/test_logging.py -v

# After 1.4
pytest tests/unit/test_observability.py -v
# With live PromptLedger:
pytest tests/integration/test_observability_integration.py -v

# After 1.5
pytest tests/unit/test_spans.py -v

# After 1.6
pytest tests/unit/test_validate_prompts.py -v
python scripts/validate_prompts.py   # expects SKIP when PL not configured
```

Full suite at epic completion:
```bash
pytest tests/unit -v --tb=short
ruff check src/ tests/
```

---

## Critical Files

**NEW:**
- `pyproject.toml`
- `Makefile`
- `.env.example`
- `.gitignore`
- `src/srf/__init__.py`
- `src/srf/py.typed`
- `src/srf/config.py`
- `src/srf/logging.py`
- `src/srf/observability.py`
- `src/srf/spans.py`
- `src/srf/prompts/__init__.py`
- `scripts/validate_prompts.py`
- `tests/fixtures/conftest.py`
- `tests/unit/test_config.py`
- `tests/unit/test_logging.py`
- `tests/unit/test_observability.py`
- `tests/unit/test_spans.py`
- `tests/unit/test_validate_prompts.py`
- `tests/integration/test_observability_integration.py`
