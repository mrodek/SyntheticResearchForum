# SRF Progress Tracker

Newest entries first. Each entry references the epic/story, files changed, and decisions made.

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
