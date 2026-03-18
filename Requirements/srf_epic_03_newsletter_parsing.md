# Epic 3: Newsletter Parsing & Forum Config Generation

## Prerequisites

Epic 1 (Foundation) — complete. `SRFConfig`, structured logging, `log_span`, `build_tracker`, and the prompt registration infrastructure from Story 1.6 are all required before this epic begins.

---

## Context

The SRF debate pipeline begins when a newsletter issue identifies a set of papers and frames the intellectual tensions between them. Before any agent can prepare for a debate, the system must parse a newsletter file into structured paper references, cluster those references by the thematic tensions the newsletter editor has already identified, and generate one or two candidate forum config files that capture the debate topic, paper list, and framing question. Without this parsing layer, every forum config must be hand-authored — an error-prone bottleneck that defeats the automated pipeline.

---

## What We Gain

| Gap (before) | After this epic |
|---|---|
| No structured representation of newsletter content | `NewsletterDoc` dataclass with parsed papers, tensions, supporting evidence, and narrative |
| Forum configs hand-authored from newsletter notes | Candidate configs auto-generated via two focused LLM calls: semantic clustering and framing question composition |
| No canonical location for draft configs | `data/workspace/candidates/{newsletter_slug}/` with versioned JSON files |
| LLM calls invisible to observability | Every clustering and framing call logged as a `SpanPayload` to PromptLedger |
| No CLI entrypoint for the parsing workflow | `scripts/parse_newsletter.py --file newsletter.md` produces ready-to-review configs |

---

## Architecture Decisions

### Newsletter is the editorial layer — LLM calls are composition and semantic mapping, not generation

The newsletter already performs the editorial framing work. Pattern Watch items are debate tension axes; the issue subtitle is the topic; This Week's Signal is the debate brief; Primary Signals contain per-paper technical summaries and significance assessments. This epic makes two focused LLM calls: one to semantically map papers to tension axes (clustering), and one to compose a framing question from the selected papers and tensions. Neither call generates claims, summaries, or debate positions — those come from the papers themselves in Epic 4.

### Clustering uses an LLM, not keyword overlap

Paper summaries and Pattern Watch axes are written by the same editorial author but use different vocabulary. A paper about "optimisation pressure degrading safety margins" addresses the "efficiency vs alignment" axis — but keyword matching would miss it. Semantic matching via LLM is the correct tool for this assignment. The clustering call is a single structured prompt that receives all paper summaries and all tension axes and returns a JSON mapping; it is not a per-paper loop. Both the clustering span and the framing span are logged to PromptLedger.

### arXiv URLs are the paper identity key

Newsletter issues use `arxiv.org/abs/{id}` in various formats (with and without version suffix, with and without `v1`). The parser normalises all variants to a canonical `arxiv_id` (`NNNN.NNNNN`). Non-arXiv preprint URLs (e.g. `osf.io/preprints/`, `osf.io/`) are preserved verbatim with `source="other"` and a warning log — they are included in the candidate config but flagged for manual review in Epic 4 (PDF extraction).

### Two LLM calls per newsletter run, not per paper

The clustering call happens once per newsletter (maps all papers to all axes in a single structured prompt). The framing call happens once per candidate config (one or two per newsletter). Paper summaries come directly from the newsletter `**Technical summary:**` fields. This keeps token costs and latency predictable regardless of paper count, and keeps the observability footprint minimal — one clustering span plus one framing span per config.

### Candidate configs are drafts, not approved forums

Output of this epic is `CandidateForumConfig` JSON files. They require editorial approval (Epic 8) before becoming live forum configs. The schema is a strict subset of the full `ForumConfig` from Epic 4 — fields that depend on PDF extraction are absent and defaulted.

### Both prompts registered at startup, both calls route through tracker.execute()

Both the clustering prompt (`newsletter.paper_clustering`) and the framing question prompt (`newsletter.framing_question`) are defined in `src/srf/prompts/newsletter.py` and registered via `register_prompts()` at startup. Both LLM calls go through `tracker.execute()` (Mode 2) — PL makes the provider call and auto-creates the span, returning `result.response_text` + writing `state["last_span_id"]`. When `tracker=None`, the system calls the provider directly via `call_provider_directly()` (defined in Epic 5, Story 5.1). Unit tests mock `tracker.execute()` and never touch provider SDKs.

---

## Stories

---

### Story 3.1 — Newsletter Parser

**As a** system,
**I would like** a parser that reads a Markdown newsletter file and returns a structured `NewsletterDoc` object,
**so that** downstream stories can work with typed data rather than raw Markdown strings.

**Files:**
- NEW: `src/srf/newsletter/__init__.py`
- NEW: `src/srf/newsletter/parser.py`
- NEW: `src/srf/newsletter/models.py`
- NEW: `tests/unit/test_newsletter_parser.py`
- NEW: `tests/fixtures/newsletters/` _(copy of representative newsletter fixtures)_

**Acceptance Criteria:**

```gherkin
Scenario: parser extracts issue metadata from header
  Given a newsletter file with header "## Issue #5 — Multi-Agent Systems Under Stress"
  When  parse_newsletter(path) is called
  Then  result.issue_number equals 5
  And   result.subtitle equals "Multi-Agent Systems Under Stress"

Scenario: parser extracts all Primary Signal papers
  Given a newsletter file with three Primary Signals sections
  When  parse_newsletter(path) is called
  Then  result.primary_signals has length 3
  And   each PrimarySignal has non-empty title, arxiv_id, technical_summary, and why_it_matters

Scenario: parser normalises arxiv URL with version suffix to bare arxiv_id
  Given a Primary Signal with URL "https://arxiv.org/abs/2401.12345v2"
  When  parse_newsletter(path) is called
  Then  the corresponding PrimarySignal.arxiv_id equals "2401.12345"
  And   PrimarySignal.source equals "arxiv"

Scenario: parser normalises arxiv URL without version suffix
  Given a Primary Signal with URL "https://arxiv.org/abs/2401.12345"
  When  parse_newsletter(path) is called
  Then  the corresponding PrimarySignal.arxiv_id equals "2401.12345"

Scenario: parser flags non-arxiv preprint URLs
  Given a Primary Signal with URL "https://osf.io/preprints/psyarxiv/8hbp9_v1/"
  When  parse_newsletter(path) is called
  Then  PrimarySignal.source equals "other"
  And   PrimarySignal.url equals "https://osf.io/preprints/psyarxiv/8hbp9_v1/"
  And   PrimarySignal.arxiv_id is None

Scenario: parser extracts Pattern Watch tension axes
  Given a newsletter with three Pattern Watch items
  When  parse_newsletter(path) is called
  Then  result.pattern_watch is a list of 3 non-empty strings

Scenario: parser extracts Supporting Evidence bullets
  Given a newsletter with five Supporting Evidence bullets
  When  parse_newsletter(path) is called
  Then  result.supporting_evidence has length 5
  And   each SupportingEvidenceItem has a non-empty description

Scenario: parser extracts This Week's Signal narrative
  Given a newsletter with a "This Week's Signal" section
  When  parse_newsletter(path) is called
  Then  result.signal_narrative is a non-empty string

Scenario: parser raises ParseError on file not found
  Given a path that does not exist
  When  parse_newsletter(path) is called
  Then  it raises ParseError with a message containing the path

Scenario: parser raises ParseError when no Primary Signals are found
  Given a Markdown file with no "### " headings matching the Primary Signal pattern
  When  parse_newsletter(path) is called
  Then  it raises ParseError with a message indicating no papers were found

Scenario: parser raises ParseError when Pattern Watch section is absent
  Given a Markdown file with no "Pattern Watch" section
  When  parse_newsletter(path) is called
  Then  it raises ParseError with a message indicating the missing section
```

**TDD Notes:** Create minimal Markdown fixtures in `tests/fixtures/newsletters/` — not copies of the full real newsletters. Each fixture should be the smallest valid input that exercises one scenario. Use `tmp_path` for file-not-found tests.

---

### Story 3.2 — Paper Candidate Clustering

**As a** system,
**I would like** a clustering function that uses an LLM to semantically assign Primary Signal papers to Pattern Watch tension axes,
**so that** forum config generation receives a coherent, editorially-grounded paper set for each candidate debate even when paper summaries use different vocabulary from the tension axis labels.

**Context:** The newsletter author writes Pattern Watch axes and paper summaries independently. Keyword overlap is unreliable — a paper about "optimisation pressure degrading safety margins" addresses "efficiency vs alignment" but shares no keywords. A single structured LLM call mapping all papers to all axes in one prompt is the correct approach. This call must be logged to PromptLedger.

**Files:**
- NEW: `src/srf/newsletter/clustering.py`
- MODIFY: `src/srf/prompts/newsletter.py`
- NEW: `tests/unit/test_newsletter_clustering.py`

**Acceptance Criteria:**

```gherkin
Scenario: cluster_papers returns one PaperCluster per tension axis that has at least two papers
  Given a NewsletterDoc with 3 Pattern Watch tensions and 4 Primary Signals
  And   a mock tracker whose execute coroutine returns a valid ExecutionResult with axis-to-papers JSON
  When  cluster_papers(doc, tracker=mock_tracker, config=config, state={"trace_id": "t1"}) is called
  Then  the result contains one PaperCluster per axis that received at least 2 papers

Scenario: cluster_papers calls tracker.execute with the clustering prompt name when tracker is provided
  Given a NewsletterDoc with 2 tensions and 3 papers
  And   a mock tracker whose execute coroutine returns a valid ExecutionResult
  When  cluster_papers(doc, tracker=mock_tracker, config=config, state={"trace_id": "t1"}) is called
  Then  mock_tracker.execute was called once with prompt_name="newsletter.paper_clustering"
  And   the messages argument contains each tension axis string from pattern_watch
  And   the messages argument contains each paper title and technical_summary
  And   it was called with mode="mode2"

Scenario: cluster_papers writes last_span_id to state after tracker.execute
  Given a mock tracker whose execute coroutine returns ExecutionResult with span_id="span-cluster-001"
  And   state = {"trace_id": "t1"}
  When  cluster_papers(doc, tracker=mock_tracker, config=config, state=state) is called
  Then  state["last_span_id"] equals "span-cluster-001"

Scenario: cluster_papers completes without error when tracker is None
  Given a valid NewsletterDoc
  And   call_provider_directly returns a valid axis-to-papers mapping JSON
  When  cluster_papers(doc, tracker=None, config=config, state={}) is called
  Then  it returns a list of PaperCluster objects without raising
  And   no PromptLedger endpoint is called

Scenario: a paper may appear in multiple clusters when the LLM assigns it to multiple axes
  Given a mock tracker whose execute coroutine assigns paper A to both "efficiency vs alignment" and "centralised control"
  When  cluster_papers(doc, tracker=mock_tracker, config=config, state={}) is called
  Then  paper A appears in both returned PaperCluster objects

Scenario: cluster_papers drops axes with fewer than two assigned papers and logs a warning
  Given a mock tracker whose execute coroutine assigns only one paper to tension axis "X"
  When  cluster_papers(doc, tracker=mock_tracker, config=config, state={}) is called
  Then  no PaperCluster is returned for axis "X"
  And   a WARNING is logged indicating axis "X" was dropped due to insufficient papers

Scenario: cluster_papers propagates a 5xx error from tracker.execute
  Given a mock tracker whose execute coroutine raises httpx.HTTPStatusError(status=503)
  When  cluster_papers(doc, tracker=mock_tracker, config=config, state={}) is called
  Then  httpx.HTTPStatusError propagates to the caller
  And   no PaperCluster objects are returned

Scenario: cluster_papers raises ClusteringError when the LLM returns malformed JSON
  Given a mock tracker whose execute coroutine returns ExecutionResult with response_text="not-json"
  When  cluster_papers(doc, tracker=mock_tracker, config=config, state={}) is called
  Then  it raises ClusteringError with a message indicating the parse failure

Scenario: cluster_papers raises ClusteringError when fewer than 2 Primary Signals exist
  Given a NewsletterDoc with only 1 Primary Signal
  When  cluster_papers(doc, tracker=None, config=config, state={}) is called
  Then  it raises ClusteringError before making any LLM call
  And   no outbound HTTP requests are made

Scenario: clustering prompt is registered in the prompt registry
  Given the SRF package is imported
  When  the prompt registry in src/srf/prompts/newsletter.py is inspected
  Then  a prompt with name "newsletter.paper_clustering" exists
  And   its template contains "{tension_axes}" and "{paper_summaries}" interpolation slots
```

**TDD Notes:** Mock `tracker.execute` using `mock_tracker.execute = AsyncMock(return_value=ExecutionResult(response_text="...", span_id="span-001", ...))`. Never mock provider SDKs in unit tests. The clustering prompt must instruct the LLM to return structured JSON — define and document the expected schema in `clustering.py` and test the parse step (from `result.response_text` to `PaperCluster` list) separately. The "fewer than 2 papers" guard must short-circuit before any execute() call. For the `tracker=None` path, patch `call_provider_directly` at the import site.

---

### Story 3.3 — Forum Config Generation

**As a** system,
**I would like** a config generation function that takes a `PaperCluster` and produces a `CandidateForumConfig` with a framing question generated by a single focused LLM call,
**so that** each candidate debate has a coherent topic, paper list, and framing question ready for editorial review.

**Context:** This story contains the framing question LLM call — the second of the two LLM calls in Epic 3. When `tracker` is provided, the call goes through `tracker.execute()` which makes the provider call and auto-creates the span. When `tracker=None`, the system calls the provider directly via `call_provider_directly()`. Both paths must generate a valid config.

**Files:**
- NEW: `src/srf/newsletter/config_generator.py`
- NEW: `src/srf/prompts/newsletter.py`
- NEW: `tests/unit/test_newsletter_config_generator.py`
- MODIFY: `src/srf/prompts/__init__.py`

**Acceptance Criteria:**

```gherkin
Scenario: generate_candidate_config returns a CandidateForumConfig with all required fields
  Given a valid PaperCluster with 3 papers and a tension axis string
  And   a mock tracker whose execute coroutine returns ExecutionResult with a framing question string
  When  generate_candidate_config(cluster, tracker=mock_tracker, config=config, state={"trace_id": "t1"}) is called
  Then  result.topic is a non-empty string derived from the cluster tension
  And   result.framing_question is the response_text from the ExecutionResult
  And   result.paper_refs contains arxiv_id for each paper in the cluster
  And   result.generated_at is an ISO-8601 timestamp string

Scenario: generate_candidate_config calls tracker.execute with the framing prompt name
  Given a valid PaperCluster
  And   a mock tracker whose execute coroutine returns a valid ExecutionResult
  When  generate_candidate_config(cluster, tracker=mock_tracker, config=config, state={"trace_id": "t1"}) is called
  Then  mock_tracker.execute was called once with prompt_name="newsletter.framing_question"
  And   the messages argument contains each paper title from the cluster
  And   the messages argument contains each Pattern Watch tension string from the cluster
  And   it was called with mode="mode2"

Scenario: generate_candidate_config writes last_span_id to state after tracker.execute
  Given a mock tracker whose execute coroutine returns ExecutionResult with span_id="span-framing-001"
  And   state = {"trace_id": "t1"}
  When  generate_candidate_config(cluster, tracker=mock_tracker, config=config, state=state) is called
  Then  state["last_span_id"] equals "span-framing-001"

Scenario: generate_candidate_config completes without error when tracker is None
  Given a valid PaperCluster
  And   call_provider_directly returns a non-empty framing question string
  When  generate_candidate_config(cluster, tracker=None, config=config, state={}) is called
  Then  it returns a CandidateForumConfig without raising
  And   no PromptLedger endpoint is called

Scenario: generate_candidate_config propagates a 5xx error from tracker.execute
  Given a mock tracker whose execute coroutine raises httpx.HTTPStatusError(status=503)
  When  generate_candidate_config(cluster, tracker=mock_tracker, config=config, state={}) is called
  Then  httpx.HTTPStatusError propagates to the caller
  And   no CandidateForumConfig is returned

Scenario: generate_candidate_config raises ConfigGenerationError when LLM returns empty string
  Given a mock tracker whose execute coroutine returns ExecutionResult with response_text=""
  When  generate_candidate_config(cluster, tracker=mock_tracker, config=config, state={}) is called
  Then  it raises ConfigGenerationError with a message indicating the empty LLM response

Scenario: framing question prompt is registered in the prompt registry
  Given the SRF package is imported
  When  the prompt registry in src/srf/prompts/newsletter.py is inspected
  Then  a prompt with name "newsletter.framing_question" exists
  And   its template contains "{tension_axes}" and "{paper_titles}" interpolation slots
```

**TDD Notes:** Mock `tracker.execute` using `AsyncMock(return_value=ExecutionResult(response_text="...", span_id="span-001", ...))`. Never mock provider SDKs in unit tests. For the `tracker=None` path, patch `call_provider_directly` at the import site. `SpanPayload` construction is no longer needed in `config_generator.py` — `tracker.execute()` handles telemetry automatically.

---

### Story 3.4 — Candidate Config Persistence & CLI Entrypoint

**As a** developer,
**I would like** a CLI script that runs the full parse → cluster → generate pipeline and writes candidate configs to the workspace,
**so that** the newsletter processing workflow can be triggered manually and the outputs are ready for editorial review.

**Files:**
- NEW: `src/srf/newsletter/persistence.py`
- MODIFY: `scripts/parse_newsletter.py`
- NEW: `tests/unit/test_newsletter_persistence.py`
- NEW: `tests/integration/test_parse_newsletter_cli.py`

**Acceptance Criteria:**

```gherkin
Scenario: save_candidate_configs writes one JSON file per candidate config
  Given two CandidateForumConfig objects and a workspace root path
  When  save_candidate_configs(configs, workspace_root, newsletter_slug="issue_5") is called
  Then  two files exist under workspace_root/candidates/issue_5/
  And   each file is named "candidate_{N}.json" where N is the 1-based index

Scenario: saved JSON files are valid CandidateForumConfig when parsed
  Given a CandidateForumConfig saved via save_candidate_configs
  When  the written JSON file is read and parsed
  Then  it deserialises to an equivalent CandidateForumConfig without error

Scenario: save_candidate_configs creates the output directory if absent
  Given a workspace root where the candidates directory does not exist
  When  save_candidate_configs(configs, workspace_root, newsletter_slug="issue_1") is called
  Then  the directory workspace_root/candidates/issue_1/ is created
  And   the config files are written successfully

Scenario: save_candidate_configs raises PersistenceError when workspace root is not writable
  Given a workspace root path that is read-only
  When  save_candidate_configs(configs, workspace_root, newsletter_slug="x") is called
  Then  it raises PersistenceError with a message containing the workspace path

Scenario: CLI script parse_newsletter.py exits 0 and prints config file paths on success
  Given a valid newsletter file and a writable workspace root set in the environment
  When  scripts/parse_newsletter.py --file <newsletter_path> is run
  Then  it exits with code 0
  And   stdout contains the path of each written candidate config file

Scenario: CLI script exits 1 and prints an error when the newsletter file is not found
  Given a --file argument pointing to a non-existent path
  When  scripts/parse_newsletter.py --file missing.md is run
  Then  it exits with code 1
  And   stderr contains a message indicating the file was not found

Scenario: CLI script exits 1 and prints an error when parsing fails
  Given a Markdown file that is missing the Pattern Watch section
  When  scripts/parse_newsletter.py --file <bad_newsletter> is run
  Then  it exits with code 1
  And   stderr contains the ParseError message

Scenario: CLI script skips PromptLedger span submission and exits 0 when PROMPTLEDGER_API_URL is absent
  Given PROMPTLEDGER_API_URL is not set in the environment
  When  scripts/parse_newsletter.py --file <valid_newsletter> is run
  Then  it exits with code 0
  And   stdout contains the path of each written candidate config file

Scenario: CLI script accepts --dry-run flag and prints configs without writing files
  Given a valid newsletter file
  When  scripts/parse_newsletter.py --file <newsletter_path> --dry-run is run
  Then  it exits with code 0
  And   no files are written to the workspace
  And   stdout contains the serialised candidate config JSON
```

**TDD Notes:** The integration test (`test_parse_newsletter_cli.py`) uses `subprocess.run` against the real script with a real fixture file from `tests/fixtures/newsletters/`. It requires `SRF_LLM_PROVIDER`, `SRF_LLM_MODEL`, and `SRF_LLM_API_KEY` to be set — skip with `pytest.mark.skipif` when absent. Unit tests for `persistence.py` use `tmp_path`. The `--dry-run` scenario is unit-testable by mocking `save_candidate_configs`.

---

### Story 3.5 — MCP Trigger Tool

**As a** developer,
**I would like** an MCP tool that Claude Desktop can invoke to copy a newsletter file from the ResearchKG directory into SRF and trigger the parse → cluster → generate pipeline,
**so that** publishing a newsletter in ResearchKG automatically initiates the SRF forum candidate generation without manual CLI steps.

**Context:** This story is the integration point between the ResearchKG newsletter workflow (Claude Desktop) and the SRF pipeline. The trigger deliberately stops after candidate config generation — it does not advance into workspace setup or debate. The candidate configs are returned to Claude Desktop for editorial review before the pipeline proceeds. This enforces the human gate between Epic 3 and Epic 4.

**Files:**
- NEW: `src/srf/mcp/__init__.py`
- NEW: `src/srf/mcp/tools.py`
- NEW: `tests/unit/test_mcp_tools.py`
- NEW: `tests/integration/test_mcp_trigger.py`

**Acceptance Criteria:**

```gherkin
Scenario: trigger_newsletter_forum copies the newsletter file to the SRF newsletters directory
  Given a valid newsletter file at a source path in the ResearchKG directory
  When  trigger_newsletter_forum(source_path, workspace_root) is called
  Then  the file is copied to SRF_WORKSPACE_ROOT/.newsletters/{filename}
  And   the original file at source_path is unchanged

Scenario: trigger_newsletter_forum returns candidate config summaries on success
  Given a valid newsletter file and a mock parse pipeline that returns two CandidateForumConfigs
  When  trigger_newsletter_forum(source_path, workspace_root) is called
  Then  the return value contains a list of candidate config file paths
  And   each entry includes topic, framing_question, and paper count
  And   status equals "awaiting_approval"

Scenario: trigger_newsletter_forum does not advance the pipeline beyond candidate generation
  Given a valid newsletter file
  When  trigger_newsletter_forum(source_path, workspace_root) is called
  Then  no workspace setup, paper extraction, or debate phases are initiated
  And   no forum_id is assigned

Scenario: trigger_newsletter_forum raises ToolError when source file does not exist
  Given a source_path that does not exist
  When  trigger_newsletter_forum(source_path, workspace_root) is called
  Then  it raises ToolError with a message containing the missing path

Scenario: trigger_newsletter_forum raises ToolError when a newsletter with the same slug already exists
  Given a newsletter file with slug "issue_5" that has already been processed
  When  trigger_newsletter_forum(source_path, workspace_root) is called
  Then  it raises ToolError with a message indicating the duplicate slug
  And   no files are overwritten

Scenario: trigger_newsletter_forum is exposed as an MCP tool with the correct schema
  Given the SRF MCP server is initialised
  When  the tool list is inspected
  Then  a tool named "trigger_newsletter_forum" is present
  And   it declares parameters: source_path (string, required) and workspace_root (string, optional)
  And   its description mentions "newsletter" and "candidate configs"

Scenario: trigger_newsletter_forum logs the pipeline run to structured logging
  Given a valid newsletter file
  When  trigger_newsletter_forum(source_path, workspace_root) is called
  Then  a structured log entry is emitted at INFO level containing the newsletter slug
  And   a structured log entry is emitted at INFO level containing the number of candidate configs generated
```

**TDD Notes:** The MCP tool wraps the same `parse_newsletter` → `cluster_papers` → `generate_candidate_config` → `save_candidate_configs` pipeline built in Stories 3.1–3.4. Unit tests mock the pipeline functions — do not re-test the pipeline logic here. The duplicate-slug guard reads the `.newsletters/` directory for existing filenames. The integration test invokes the tool directly (not via MCP protocol) with a real fixture file; it requires `SRF_LLM_PROVIDER`, `SRF_LLM_MODEL`, and `SRF_LLM_API_KEY`.

---

## Implementation Order

```
Story 3.1 (newsletter parser + models)
  → Story 3.2 (clustering — depends on NewsletterDoc from 3.1)
    → Story 3.3 (config generation — depends on PaperCluster from 3.2)
      → Story 3.4 (persistence + CLI — depends on CandidateForumConfig from 3.3)
        → Story 3.5 (MCP trigger — wraps the full 3.1–3.4 pipeline)
```

All five stories are sequential. Story 3.5 depends on the complete pipeline from Stories 3.1–3.4.

---

## Verification Checklist

```bash
# After 3.1
pytest tests/unit/test_newsletter_parser.py -v

# After 3.2
pytest tests/unit/test_newsletter_clustering.py -v
# Verify clustering prompt is registered:
python -c "from srf.prompts.newsletter import NEWSLETTER_PROMPTS; print([p.name for p in NEWSLETTER_PROMPTS])"
# Expects: ['newsletter.paper_clustering']

# After 3.3
pytest tests/unit/test_newsletter_config_generator.py -v
# Verify both prompts registered:
python -c "from srf.prompts.newsletter import NEWSLETTER_PROMPTS; print([p.name for p in NEWSLETTER_PROMPTS])"
# Expects: ['newsletter.paper_clustering', 'newsletter.framing_question']

# After 3.4
pytest tests/unit/test_newsletter_persistence.py -v
python scripts/parse_newsletter.py --file .newsletters/weekly_field_notes_issue_1.md --dry-run
# Expects: printed JSON with topic, framing_question, paper_refs

# After 3.5
pytest tests/unit/test_mcp_tools.py -v
# Verify MCP tool is registered:
python -c "from srf.mcp.tools import SRF_MCP_TOOLS; print([t.name for t in SRF_MCP_TOOLS])"
# Expects: ['trigger_newsletter_forum']

# Full epic suite
pytest tests/unit -v --tb=short
ruff check src/ tests/
# With live LLM + PL configured:
pytest tests/integration/test_parse_newsletter_cli.py -v
pytest tests/integration/test_mcp_trigger.py -v
```

---

## Critical Files

**NEW:**
- `src/srf/newsletter/__init__.py`
- `src/srf/newsletter/models.py`
- `src/srf/newsletter/parser.py`
- `src/srf/newsletter/clustering.py`
- `src/srf/newsletter/config_generator.py`
- `src/srf/newsletter/persistence.py`
- `src/srf/mcp/__init__.py`
- `src/srf/mcp/tools.py`
- `src/srf/prompts/newsletter.py`
- `scripts/parse_newsletter.py`
- `tests/unit/test_newsletter_parser.py`
- `tests/unit/test_newsletter_clustering.py`
- `tests/unit/test_newsletter_config_generator.py`
- `tests/unit/test_newsletter_persistence.py`
- `tests/unit/test_mcp_tools.py`
- `tests/integration/test_parse_newsletter_cli.py`
- `tests/integration/test_mcp_trigger.py`
- `tests/fixtures/newsletters/` _(minimal fixture files)_

**MODIFY:**
- `src/srf/prompts/__init__.py`
