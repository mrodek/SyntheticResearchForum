# SRF Progress Tracker

Newest entries first. Each entry references the epic/story, files changed, and decisions made.

---

## [2026-03-19] - Railway Deployment Fixes & Dockerfile

### Summary
- Added `Dockerfile` — Node.js 20 base with Python 3.11 installed; builds OpenClaw, Lobster, and SRF Python package at image build time
- Simplified `railway.toml` startCommand to `openclaw start` (installs now happen at build, not runtime)
- Fixed 5 pre-deploy blockers identified during deploy readiness review:
  1. `railway.toml` — added `pip install + npm install @clawdbot/openclaw` to startCommand (now moved to Dockerfile)
  2. `scripts/validate_and_stage_forum.py` — trigger JSON now includes `config_path` so `run_workspace_setup.py` can read it
  3. `config/openclaw.json` — skills loader now checks `./skills` (repo) before `/data/workspace/skills` (volume)
  4. `config/exec-approvals.json` — added bare `python` and `python3` to exec allowlist
  5. `CLAUDE.md` — added "Definition of Complete" hard rule to prevent stories being marked complete without verification
- Added `Requirements/Railway/RAILWAY_SETUP_GUIDE.md` — step-by-step Railway configuration guide
- Reopened Story 1.1.5 (CI Pipeline) — was incorrectly marked Complete; `.github/workflows/ci.yml` never existed

### Decisions
- **Dockerfile over railpack** — Railway's railpack auto-detector only installed Python (not Node.js); Dockerfile gives explicit control over both runtimes
- **Install at build time not runtime** — moves `npm install` and `pip install` to Docker build layer so failures surface in build logs and startup is instant
- **Node.js 20 base image** — OpenClaw requires Node >= 20; Python 3.11 added via apt on top

### Issues & Resolution
- Railway build used railpack, detected Python-only project, installed Python 3.13 via mise but not Node.js → `openclaw` never installed → healthcheck failed on every attempt
- Fix: `Dockerfile` with `node:20-slim` base + `python3.11` apt install

### Next Steps
- [ ] Push Dockerfile + fixes → confirm Railway build succeeds and `/health` passes
- [ ] Run `/setup` wizard at `https://<service>.up.railway.app/setup`
- [ ] Run `python scripts/srf_init.py` via OpenClaw exec tool
- [ ] Story 1.1.5 — implement `.github/workflows/ci.yml` (TDD)
- [ ] Begin Epic 6: Debate Engine

---

## [2026-03-19] - Story 1.1.5 Reopened: CI Pipeline Never Implemented

### Summary
- Story 1.1.5 (CI Pipeline & Deployment Documentation) was incorrectly marked Complete on 2026-03-19
- `.github/workflows/ci.yml` was never created — the story's primary deliverable is missing
- Story moved back to `Not Started` in `progress_summary.md`
- `CLAUDE.md` updated with a hard "Definition of Complete" rule to prevent recurrence

### Issues & Resolution
- Root cause: story marked Complete without verifying all `Files:` block entries exist in the repo
- Fix: added explicit pre-completion checklist to `CLAUDE.md` §4 (Progress Tracking)

### Next Steps
- [ ] Story 1.1.5 — write `tests/unit/test_ci_workflow.py` (RED), then create `.github/workflows/ci.yml` (GREEN)
- [ ] Enable "Wait for CI" in Railway once workflow is live

---

## [2026-03-19] - Epic 5 Complete: Agent Preparation Phase

### Summary
- Epic 5, Stories 5.1–5.5 — all GREEN; 165 unit tests pass, 4 skipped
- **New (src):** `src/srf/llm/__init__.py`, `src/srf/llm/fallback.py`; `src/srf/agents/{__init__,models,roster,preparation,orchestrator}.py`; `src/srf/prompts/agents.py`
- **Modified (src):** `src/srf/prompts/__init__.py` (+`ALL_PROMPTS` aggregating newsletter + agent prompts); `src/srf/config.py` (+`paper_token_budget`, `max_prep_retries`)
- **New (scripts):** `scripts/run_preparation.py` — reads paper extraction JSON from stdin, runs parallel preparation via `asyncio.gather()`, emits preparation summary JSON to stdout
- **Modified (scripts):** `scripts/srf_init.py` — added new config fields to inline `SRFConfig` construction
- **Modified (workflows):** `workflows/srf_forum.yaml` — `agent_preparation` step wired to `python scripts/run_preparation.py`
- **New (tests):** `tests/unit/test_llm_fallback.py` (6 tests), `test_agent_roster.py` (6), `test_paper_agent_preparation.py` (7), `test_moderator_challenger_preparation.py` (7), `test_preparation_orchestrator.py` (5), `test_run_preparation.py` (2)
- **New (tests/integration):** `test_llm_fallback_integration.py`, `test_preparation_integration.py`
- **Modified (pyproject.toml):** Added optional `anthropic` and `openai` dependency groups

### Decisions
- **`call_provider_directly()` is the tracker=None fallback only** — primary LLM path is always `tracker.execute()`; provider SDKs lazy-imported inside function body so module imports cleanly without SDKs installed
- **`LLMError` wraps provider exceptions** — prevents provider-specific exceptions leaking into caller code; carries status code context for debugging
- **`list[PaperContent]` directly in `build_roster()`** — no ExtractionResult wrapper; simpler contract confirmed before implementation
- **`{memory_block}` slot in all preparation prompts** — always empty string in this epic; Epic 2 populates without template changes
- **Paper text truncated at sentence boundary** — `_budget_paper_text()` finds the last `.`/`!`/`?` at or before `SRF_PAPER_TOKEN_BUDGET` chars; logs WARNING with arxiv_id and chars_dropped
- **Moderator failure aborts; Challenger degrades gracefully** — Moderator is the routing control plane; Challenger is valuable but not structurally required
- **Moderator and Challenger receive summaries/abstracts only** — not full paper text; keeps token usage proportional to role
- **`asyncio.gather(return_exceptions=True)`** — all preparations fan out concurrently; exceptions collected and processed per-agent
- **`paper_token_budget` and `max_prep_retries` added to SRFConfig** — from `SRF_PAPER_TOKEN_BUDGET` (default 80000) and `SRF_MAX_PREP_RETRIES` (default 3) env vars
- **`ALL_PROMPTS` aggregated in `src/srf/prompts/__init__.py`** — single import point for `srf_init.py` prompt registration

### Issues & Resolution
- ruff auto-fix (SIM117) corrupted two tests by merging `with patch(...)` and `with pytest.raises(...)` blocks — fixed by combining into single `with (...)` using parenthesised form
- B905 `zip()` without `strict=` — fixed by adding `strict=True` to `zip()` calls in orchestrator and test
- `SRFConfig` field addition broke existing tests using inline construction — updated `test_llm_fallback.py`, `srf_init.py` to include `paper_token_budget` and `max_prep_retries`

### Next Steps
- [ ] Story 1.1.3 — `scripts/validate_and_stage_forum.py`
- [ ] Story 1.1.4 — Three OpenClaw Skills (SKILL.md files)
- [ ] Story 1.1.5 — `.github/workflows/ci.yml` + `.env.example` update
- [ ] Epic 6: Debate Engine: Core Discussion Loop (depends on Epic 5 complete — ✓)

---

## [2026-03-18] - Epic 1.1 Stories 1.1.1–1.1.2: Runtime Infrastructure GREEN

### Summary
- Epic 1.1, Stories 1.1.1 and 1.1.2 — all GREEN; 118 unit tests pass, 4 skipped
- **New (config):** `railway.toml`, `config/openclaw.json`, `config/exec-approvals.json`
- **New (scripts):** `scripts/srf_init.py` — validates required env vars, creates workspace subdirs, builds PromptLedger tracker, registers prompts; idempotent; exits 1 on missing required vars
- **New (tests):** `tests/unit/test_runtime_deps.py` (11 tests, 1 skipped), `tests/unit/test_srf_init.py` (6 tests)
- **Modified:** `pyproject.toml` (+`tomli>=2.0.0; python_version < '3.11'`)
- Commits: `b3545af` (Story 1.1.1), this commit (Story 1.1.2)

### Decisions
- **OpenClaw is Node.js** — deployed via Railway one-click template; `railway.toml` adds Lobster install step (`npm install -g @clawdbot/lobster`) and healthcheck config
- **`OPENCLAW_WORKSPACE_DIR`** replaces old `SRF_WORKSPACE_ROOT` as the primary workspace env var for the init script; `srf.config.SRFConfig` retains `SRF_WORKSPACE_ROOT` for the Python agent runtime
- **Python in exec-approvals, not safeBins** — OpenClaw docs exclude interpreters from `safeBins`; Python paths must be in `exec-approvals.json` allowlist instead
- **`srf_init.py` uses subprocess-compatible output** — both structlog (stderr) and explicit `print("SRF init complete")` (stdout) so tests can detect success in either stream
- **Tests use Python 3.11** — `srf` package requires Python 3.11+; the Anaconda 3.9 env cannot install it; tests must be run with `py -3.11 -m pytest`

### Issues & Resolution
- `tomllib` import failed on Python 3.9 — fixed with `try: import tomllib except ImportError: import tomli as tomllib` + `tomli` dev dep
- `import srf_init` in test_srf_init_calls_register_prompts always failed (scripts/ not on sys.path) — removed; only `importlib.util.spec_from_file_location` approach remains
- ruff F401/I001 in test file — fixed by removing unused `json`, `AsyncMock`, `os` imports and running `ruff --fix`
- pip backtracking in Python 3.9 Anaconda env — `srf` requires 3.11+; install via `py -3.11 -m pip install -e ".[dev]"`

### Next Steps
- [ ] Story 1.1.3 — `scripts/validate_and_stage_forum.py`
- [ ] Story 1.1.4 — Three OpenClaw Skills (SKILL.md files)
- [ ] Story 1.1.5 — `.github/workflows/ci.yml` + `.env.example` update

---

## [2026-03-18] - Epic 4 Complete: Workspace Management & Paper Extraction

### Summary
- Epic 4, Stories 4.1–4.4 — all GREEN; 102 unit tests pass, 3 skipped (Windows chmod)
- **New (src):** `src/srf/workspace/{__init__,models,init}.py`; `src/srf/extraction/{__init__,models,fetcher,extractor}.py`
- **New (scripts):** `scripts/run_workspace_setup.py`, `scripts/run_paper_extraction.py`
- **New (workflows):** `workflows/srf_forum.yaml` — full 9-step skeleton; workspace_setup and paper_extraction fully wired, phases 6–15 stubbed
- **New (tests):** `test_workspace_init.py`, `test_paper_fetcher.py`, `test_paper_extractor.py`, `test_run_workspace_setup.py`, `test_run_paper_extraction.py`; `tests/fixtures/papers/_builders.py`; integration stubs for fetcher and Lobster
- **Modified:** `src/srf/config.py` (+`arxiv_delay_seconds`, `min_papers`); `pyproject.toml` (+`pdfplumber`, `fpdf2`, `pyyaml`); `tests/unit/test_config.py`
- Commit: `9ae90e1`

### Decisions
- **`papers/` added to workspace subdirectories** — fetcher writes to `workspace_path/papers/`; cleaner to create it with the workspace than have the fetcher create it on demand
- **`sleep_fn` injected into fetcher** — makes rate-limit delay and retry sleep deterministic in unit tests without real waits; `asyncio.sleep` is the production default
- **Retry only on 429/5xx** — 404 means the paper doesn't exist; retrying is pointless; 429/500–504 are transient
- **`pdfplumber` over `pypdf`** — handles column layouts and academic PDF formatting more reliably; image-only PDFs (no embedded text) flagged as `extraction_status="image_only"` rather than silent empty string
- **Abstract heuristic** — finds "Abstract" or "Abstract:" header line, captures following paragraph until next short title-case line; simple but reliable for well-formatted PDFs
- **Scripts route logs to stderr** — `configure_logging(stream=sys.stderr)` called at startup so structlog output doesn't pollute the JSON stdout that Lobster reads
- **`UP035`/`UP017` ruff rules ignored** — `typing.Callable` and `timezone.utc` are idiomatic with class-level datetime imports; rules added to `[tool.ruff.lint] ignore`
- **Workflow YAML is a skeleton** — all 9 steps from the topology are present; only workspace_setup and paper_extraction are fully wired; subsequent epics MODIFY this file to replace `echo placeholder` stubs

### Issues & Resolution
- structlog defaulted to stdout, corrupting Lobster JSON output — fixed by calling `configure_logging(stream=sys.stderr)` at the top of each script's `main()`
- `datetime.UTC` alias is Python 3.11+ module-level access, not accessible as `datetime.datetime.UTC` with class import — reverted to `timezone.utc`

### Lessons Learned
- Scripts that write JSON to stdout must configure all logging to stderr before importing any library code that logs at module level

### Next Steps
- [ ] Epic 5: Agent Preparation Phase (depends on Epic 4 complete — ✓)
- [ ] Wire `call_provider_directly()` in Epic 5 Story 5.1 (referenced stub from Epic 3)
- [ ] Integration test for real arXiv fetch: `pytest tests/integration/test_paper_fetcher_integration.py -v` (requires `SRF_RUN_INTEGRATION=1`)

---

## [2026-03-18] - Git Repository Initialized

### Summary
- Initialized git repository; created initial commit `d84a316` capturing all work from Epics 1 and 3
- 69 files, 10 499 insertions
- Added `.ruff_cache/` and `.claude/settings.local.json` to `.gitignore`

### Decisions
- Single initial commit rather than reconstructed history — no prior VCS existed
- `.claude/settings.local.json` excluded (local tool config, not project state)

### Issues & Resolution
- No prior git history existed; progress_tracker bootstrapped from file state and epic documents

### Lessons Learned
- Initialize git at project start, not after Epics 1–3 are complete

### Next Steps
- [ ] Create remote repository and push
- [ ] Begin Epic 4: Workspace Management & Paper Extraction

---

## [2026-03-17] - Epic 3 Complete: Newsletter Parsing & Forum Config Generation

### Summary
- Epic 3, Stories 3.1–3.5 — all GREEN
- **New files (src):** `src/srf/newsletter/__init__.py`, `models.py`, `parser.py`, `clustering.py`, `config_generator.py`, `persistence.py`; `src/srf/mcp/__init__.py`, `server.py`, `tools.py`; `src/srf/prompts/newsletter.py`
- **New files (scripts):** `scripts/parse_newsletter.py`
- **New files (tests):** `tests/unit/test_newsletter_parser.py`, `test_newsletter_clustering.py`, `test_newsletter_config_generator.py`, `test_newsletter_persistence.py`, `test_mcp_tools.py`; `tests/fixtures/newsletters/` (4 fixture files + `_builders.py`)
- **Modified:** `src/srf/prompts/__init__.py`, `scripts/validate_prompts.py`
- Two LLM-backed prompts registered: `newsletter.paper_clustering`, `newsletter.framing_question`
- Unit test suite passes; integration tests (`test_parse_newsletter_cli.py`, `test_mcp_trigger.py`) require live env vars and skip when absent

### Decisions
- **LLM for clustering, not keyword matching** — newsletter author writes tension axes and paper summaries in different vocabulary; semantic mapping via a single structured prompt is the only reliable approach
- **Two LLM calls per newsletter run, not per paper** — clustering is one call mapping all papers to all axes; framing is one call per candidate config; token cost is O(newsletter) not O(papers)
- **`tracker.execute()` for both LLM calls** — PromptLedger makes the provider call and auto-creates the span; `SpanPayload` construction removed from call sites
- **arXiv ID as paper identity key** — all URL variants normalised to bare `NNNN.NNNNN`; non-arXiv URLs preserved verbatim with `source="other"` and a warning
- **Candidate configs are drafts, not live forums** — pipeline stops after `save_candidate_configs()`; no `forum_id` assigned until editorial approval (Epic 8)
- **MCP trigger stops at candidate generation** — enforces the human gate between Epic 3 and Epic 4; Claude Desktop receives config summaries with `status="awaiting_approval"`
- **`call_provider_directly()` stub for `tracker=None` path** — full implementation deferred to Epic 5 Story 5.1; clustering and config generation both reference it but it is not yet wired to a real provider

### Issues & Resolution
- PromptLedger CR-001 (`PL_ChangeRequest_1.md`) raised during this epic: the existing Mode 2 pattern required ~20 lines of boilerplate per call site and did not support `tracker.execute()`. CR-001 requests a unified `execute()` method on `AsyncPromptLedgerClient` — this was adopted as the call pattern for all subsequent epics. CLAUDE.md updated to reflect `tracker.execute()` as the primary call pattern.

### Lessons Learned
- Defining the `tracker.execute()` contract before implementing call sites saved significant refactoring
- Fixture Markdown files should be the minimum valid input per scenario — full newsletter copies are too large and mask parser edge cases

### Next Steps
- [ ] Epic 4: Workspace Management & Paper Extraction (depends on Epic 3 complete — ✓)
- [ ] Wire `call_provider_directly()` in Epic 5 Story 5.1

---

## [2026-03-17] - Epic 1 Complete: Foundation — Scaffold, Config, Logging, Observability

### Summary
- Epic 1, Stories 1.1–1.6 — all GREEN
- **New files (src):** `src/srf/__init__.py`, `py.typed`, `config.py`, `logging.py`, `observability.py`, `spans.py`, `prompts/__init__.py`
- **New files (scripts):** `scripts/validate_prompts.py`
- **New files (tests):** `tests/unit/test_scaffold.py`, `test_config.py`, `test_logging.py`, `test_observability.py`, `test_spans.py`, `test_validate_prompts.py`; `tests/integration/test_observability_integration.py`; `tests/fixtures/conftest.py`
- **New project files:** `pyproject.toml`, `Makefile`, `.env.example`, `.gitignore`
- All required environment variables documented in `.env.example`
- `ruff check src/ tests/` exits 0

### Decisions
- **Provider-agnostic LLM config** — `SRF_LLM_PROVIDER` / `SRF_LLM_MODEL` / `SRF_LLM_API_KEY` are the only LLM-related required vars; no provider SDK imported unconditionally; provider clients instantiated at startup based on `SRF_LLM_PROVIDER`
- **PromptLedger Mode 2, not Mode 1** — SRF calls the configured LLM provider and logs spans after the fact; Mode 1 was rejected because SRF requires full control of message construction and streaming
- **`tracker=None` injection over module-level singleton** — every function that calls PromptLedger accepts `tracker: AsyncPromptLedgerClient | None` as a parameter; makes unit testing trivially free of network calls
- **Span IDs through workflow state, not `contextvars`** — Railway sleep/wake cycles do not preserve `contextvars` across invocations; all `trace_id` and `parent_span_id` values stored in the state dict
- **`structlog` over stdlib `logging`** — JSON-lines natively, per-coroutine context binding, no thread-local issues; `print()` banned in production paths and enforced by an AST-scanning test in `test_logging.py`
- **`ConfigurationError` at startup for missing vars** — fail loudly at boot rather than silently at runtime; `SRF_LOG_LEVEL` defaults to `INFO`, `SRF_WORKSPACE_ROOT` defaults to `/data/workspace`
- **PromptLedger requires both vars or neither** — partial config (`PROMPTLEDGER_API_URL` set without `PROMPTLEDGER_API_KEY`) raises `ConfigurationError`

### Issues & Resolution
- None — Epic 1 is self-contained with no external dependencies

### Lessons Learned
- AST-scanning test for `print()` calls (`test_logging.py`) catches production logging violations at test time rather than code review
- `structlog.testing.capture_logs()` makes logging unit tests trivially fast with no I/O

### Next Steps
- [ ] Epic 3: Newsletter Parsing & Forum Config Generation (depends on Epic 1 — ✓)
