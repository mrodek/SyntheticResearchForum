# Epic 4: Workspace Management & Paper Extraction

## Prerequisites

- Epic 1 (Foundation) — complete. `SRFConfig`, `log_span`, `build_tracker`, structured logging all required.
- Epic 3 (Newsletter Parsing) — complete. `CandidateForumConfig` is the input to this epic's first story.

---

## Context

Before any agent can prepare for a debate, the system needs a stable forum workspace and the full text of every paper under discussion. Epic 3 produces candidate configs containing arXiv IDs and newsletter summaries — but newsletter summaries are editorial condensations, not the source material. Agents must reason from the actual paper content. This epic assigns the forum its identity (`forum_id`), establishes its workspace directory, fetches each paper PDF from arXiv, extracts structured text, and wires the first two Lobster workflow steps that carry this data forward.

---

## What We Gain

| Gap (before) | After this epic |
|---|---|
| No forum identity — candidate configs have no runtime ID | `forum_id` assigned at workspace creation, carried through all downstream state |
| No workspace structure — nowhere to write debate artifacts | `/data/workspace/forum/{forum_id}/` created with canonical subdirectory layout |
| Agents work from newsletter summaries only | Full paper text extracted and persisted; agents get abstract + full body |
| Non-arXiv papers silently dropped | Non-arXiv sources preserved with `extraction_status="manual_review_required"` — visible, not invisible |
| No Lobster workflow exists | `workflows/srf_forum.yaml` created with workspace and extraction steps wired |

---

## Architecture Decisions

### `forum_id` format: `forum-{YYYYMMDD}-{uuid4[:8]}`

Sortable by date, human-readable at a glance, and unique without a database. The date prefix makes log scanning and workspace browsing trivial. The short UUID suffix ensures uniqueness within a day. Forum IDs are assigned once at workspace creation and never change.

### arXiv fetching via direct PDF URL, not the arXiv API

`https://arxiv.org/pdf/{arxiv_id}` is stable, requires no authentication, and returns the canonical PDF. The arXiv API is for metadata search — not needed here since the newsletter already provides titles and summaries. arXiv's terms request a minimum 3-second delay between requests; this is enforced via `SRF_ARXIV_DELAY_SECONDS` (default `3`).

### `pdfplumber` for text extraction

`pdfplumber` handles the column layouts, figure captions, and reference sections common in academic PDFs more reliably than `pypdf`. It produces clean per-page text that can be joined into a full-document string. Scanned-image PDFs (no embedded text) produce empty extraction — these are flagged as `extraction_status="image_only"` rather than failing silently.

### Non-arXiv sources: preserve, flag, do not fetch

Papers with `source="other"` (OSF preprints etc.) cannot be fetched reliably. They are written to the workspace with `full_text=None` and `extraction_status="manual_review_required"`. Operators can manually drop the extracted text file into the workspace. The partial failure policy (below) governs whether the forum proceeds.

### Minimum viable paper set: `SRF_MIN_PAPERS` (default 2)

If fewer than `SRF_MIN_PAPERS` papers are successfully extracted, the workflow aborts and writes `forum_status="aborted"` to `state.json`. A single-paper debate is not a debate.

### Lobster scripts read stdin, write stdout — no direct filesystem access in tests

`scripts/run_workspace_setup.py` and `scripts/run_paper_extraction.py` are thin Lobster step wrappers: read JSON from `sys.stdin`, call the underlying library functions, write JSON to `sys.stdout`, exit 0 or 1. The library functions (`src/srf/workspace/`, `src/srf/extraction/`) are fully tested in isolation. Integration tests call the scripts via `subprocess.run`.

### `state.json` written at every phase boundary

Every Lobster step script writes the complete current workflow state to `{workspace_path}/state.json` before exiting. This enables manual inspection, debugging, and replay from any checkpoint without re-running earlier phases.

---

## Stories

---

### Story 4.1 — Forum Workspace Initialisation

**As a** system,
**I would like** a workspace initialisation function that accepts an approved `CandidateForumConfig`, assigns a `forum_id`, and creates the canonical workspace directory structure,
**so that** all subsequent phases have a stable, uniquely-identified location to read from and write to.

**Files:**
- NEW: `src/srf/workspace/__init__.py`
- NEW: `src/srf/workspace/models.py`
- NEW: `src/srf/workspace/init.py`
- NEW: `tests/unit/test_workspace_init.py`

**Acceptance Criteria:**

```gherkin
Scenario: initialise_workspace returns a ForumWorkspace with a valid forum_id
  Given a valid CandidateForumConfig and a writable workspace root
  When  initialise_workspace(config, workspace_root) is called
  Then  result.forum_id matches the pattern "forum-YYYYMMDD-{8 hex chars}"
  And   result.workspace_path equals workspace_root/forum/{forum_id}

Scenario: initialise_workspace creates the canonical subdirectory structure
  Given a valid CandidateForumConfig
  When  initialise_workspace(config, workspace_root) is called
  Then  the following directories exist under result.workspace_path:
        preparation/, transcripts/, synthesis/, logs/

Scenario: initialise_workspace writes state.json with status "workspace_ready"
  Given a valid CandidateForumConfig
  When  initialise_workspace(config, workspace_root) is called
  Then  state.json exists at result.workspace_path/state.json
  And   state.json contains forum_id, forum_status="workspace_ready", and created_at

Scenario: initialise_workspace raises WorkspaceError when workspace root is not writable
  Given a workspace root path that is read-only
  When  initialise_workspace(config, workspace_root) is called
  Then  it raises WorkspaceError with a message containing the workspace root path

Scenario: initialise_workspace raises WorkspaceError when a forum with the same id already exists
  Given a workspace_path that already exists at the target location
  When  initialise_workspace(config, workspace_root) is called
  Then  it raises WorkspaceError indicating a duplicate forum workspace

Scenario: ForumWorkspace serialises to and from JSON without data loss
  Given a ForumWorkspace instance
  When  it is serialised to JSON and deserialised
  Then  the result equals the original instance
```

**TDD Notes:** Use `tmp_path` for all filesystem tests. The `forum_id` pattern test should use `re.match`. The duplicate-ID scenario is unlikely in practice (UUID collision) but must be handled — test it by pre-creating the target directory.

---

### Story 4.2 — arXiv Paper Fetcher

**As a** system,
**I would like** a paper fetcher that downloads PDFs from arXiv with rate limiting and retry logic,
**so that** the workspace contains the source PDF for each paper before extraction begins.

**Files:**
- NEW: `src/srf/extraction/__init__.py`
- NEW: `src/srf/extraction/fetcher.py`
- NEW: `tests/unit/test_paper_fetcher.py`
- NEW: `tests/integration/test_paper_fetcher_integration.py`

**Acceptance Criteria:**

```gherkin
Scenario: fetch_paper downloads the PDF and writes it to the workspace
  Given a mock HTTP client returning a valid PDF byte stream for arxiv_id "2401.12345"
  When  fetch_paper(arxiv_id="2401.12345", workspace_path=tmp_path, http_client=mock_client) is called
  Then  a file exists at workspace_path/papers/2401.12345.pdf
  And   the file content equals the byte stream returned by the mock client

Scenario: fetch_paper returns FetchResult with status "ok" on success
  Given a mock HTTP client returning a valid PDF byte stream
  When  fetch_paper(arxiv_id="2401.12345", workspace_path=tmp_path, http_client=mock_client) is called
  Then  result.status equals "ok"
  And   result.arxiv_id equals "2401.12345"
  And   result.pdf_path is the path of the written file

Scenario: fetch_paper retries on HTTP 429 and succeeds on second attempt
  Given a mock HTTP client that returns 429 on the first call and 200 on the second
  When  fetch_paper(arxiv_id="2401.12345", workspace_path=tmp_path, http_client=mock_client) is called
  Then  the mock client was called exactly twice
  And   result.status equals "ok"

Scenario: fetch_paper returns FetchResult with status "failed" after all retries exhausted
  Given a mock HTTP client that always returns 503
  When  fetch_paper(arxiv_id="2401.12345", workspace_path=tmp_path, http_client=mock_client, max_retries=3) is called
  Then  the mock client was called exactly 3 times
  And   result.status equals "failed"
  And   result.error contains the HTTP status code

Scenario: fetch_paper skips fetching and returns status "manual_review_required" for non-arXiv sources
  Given a PrimarySignal with source="other" and arxiv_id=None
  When  fetch_paper_for_signal(signal, workspace_path, http_client) is called
  Then  no HTTP request is made
  And   result.status equals "manual_review_required"

Scenario: fetch_papers_for_forum respects the delay between requests
  Given a mock HTTP client and a mock sleep function
  And   SRF_ARXIV_DELAY_SECONDS is set to 1
  When  fetch_papers_for_forum(paper_refs, workspace_path, http_client) is called with 3 papers
  Then  the mock sleep function was called at least twice with value >= 1

Scenario: fetch_paper raises FetchError when workspace papers directory is not writable
  Given a workspace_path where the papers/ subdirectory is read-only
  When  fetch_paper(arxiv_id="2401.12345", workspace_path=tmp_path, http_client=mock_client) is called
  Then  it raises FetchError with a message indicating the write failure
```

**TDD Notes:** Inject `http_client` and `sleep_fn` as parameters — never call `httpx.get` or `time.sleep` directly in the fetcher. This makes rate-limiting behaviour testable without real delays. The integration test calls the real arXiv endpoint for one paper; skip when `SRF_RUN_INTEGRATION` env var is absent to avoid CI hammering arXiv.

---

### Story 4.3 — PDF Text Extraction

**As a** system,
**I would like** a text extraction function that reads a downloaded PDF and produces a structured `PaperContent` object with abstract and full body text,
**so that** agents receive the actual paper content rather than newsletter summaries.

**Files:**
- NEW: `src/srf/extraction/extractor.py`
- NEW: `tests/unit/test_paper_extractor.py`
- NEW: `tests/fixtures/papers/` _(minimal PDF fixtures)_

**Acceptance Criteria:**

```gherkin
Scenario: extract_paper_content returns a PaperContent with non-empty full_text
  Given a PDF file containing readable embedded text
  When  extract_paper_content(pdf_path) is called
  Then  result.full_text is a non-empty string
  And   result.extraction_status equals "ok"
  And   result.page_count is greater than 0

Scenario: extract_paper_content populates abstract when abstract section is detectable
  Given a PDF with a clearly labelled "Abstract" section
  When  extract_paper_content(pdf_path) is called
  Then  result.abstract is a non-empty string
  And   result.abstract is a substring of result.full_text

Scenario: extract_paper_content returns status "image_only" for a scanned PDF with no embedded text
  Given a PDF where all pages contain only images and no embedded text
  When  extract_paper_content(pdf_path) is called
  Then  result.extraction_status equals "image_only"
  And   result.full_text is None

Scenario: extract_paper_content returns status "failed" and logs a warning when pdfplumber raises
  Given a corrupt or unreadable PDF file
  When  extract_paper_content(pdf_path) is called
  Then  result.extraction_status equals "failed"
  And   result.full_text is None
  And   a WARNING is logged containing the pdf_path

Scenario: extract_paper_content does not raise when the PDF is missing
  Given a pdf_path that does not exist
  When  extract_paper_content(pdf_path) is called
  Then  result.extraction_status equals "failed"
  And   it returns without raising

Scenario: extract_papers_for_forum returns a list with one PaperContent per FetchResult
  Given 3 FetchResults with status "ok" and 1 with status "failed"
  When  extract_papers_for_forum(fetch_results, workspace_path) is called
  Then  the result contains 4 PaperContent objects
  And   the 3 successful extractions have extraction_status "ok"
  And   the 1 failed fetch has extraction_status "failed"

Scenario: extract_papers_for_forum raises ExtractionError when fewer than SRF_MIN_PAPERS succeed
  Given 1 FetchResult with status "ok" and SRF_MIN_PAPERS is 2
  When  extract_papers_for_forum(fetch_results, workspace_path) is called
  Then  it raises ExtractionError with a message indicating insufficient papers
  And   the error includes the count of successful extractions
```

**TDD Notes:** Create minimal PDF fixtures in `tests/fixtures/papers/` using `pdfplumber`'s test utilities or a small programmatically-generated PDF (via `reportlab` or `fpdf2` as a dev dependency). Do not commit large real paper PDFs. The "image_only" scenario can be tested with a PDF containing only a white rectangle drawn via code. The `SRF_MIN_PAPERS` check reads from `SRFConfig` — inject config or the value directly as a parameter.

---

### Story 4.4 — Lobster Step Scripts & Workflow Skeleton

**As a** system,
**I would like** the two Lobster step scripts for workspace setup and paper extraction, and the initial `srf_forum.yaml` workflow definition,
**so that** the Lobster orchestrator can invoke these phases as the first two steps of the forum pipeline.

**Files:**
- NEW: `scripts/run_workspace_setup.py`
- NEW: `scripts/run_paper_extraction.py`
- NEW: `workflows/srf_forum.yaml`
- NEW: `tests/unit/test_run_workspace_setup.py`
- NEW: `tests/unit/test_run_paper_extraction.py`
- NEW: `tests/integration/test_lobster_steps.py`

**Acceptance Criteria:**

```gherkin
Scenario: run_workspace_setup.py exits 0 and writes forum_id to stdout JSON
  Given valid trigger JSON on stdin containing a config_path to a valid CandidateForumConfig
  And   a writable SRF_WORKSPACE_ROOT
  When  scripts/run_workspace_setup.py is run
  Then  it exits with code 0
  And   stdout is valid JSON containing forum_id and workspace_path

Scenario: run_workspace_setup.py exits 1 and writes error to stderr on invalid config
  Given stdin JSON referencing a config_path that does not exist
  When  scripts/run_workspace_setup.py is run
  Then  it exits with code 1
  And   stderr contains a message indicating the missing config

Scenario: run_paper_extraction.py exits 0 and writes paper content summary to stdout JSON
  Given valid stdin JSON from run_workspace_setup.py with 2 papers
  And   a mock arXiv endpoint returning valid PDFs
  When  scripts/run_paper_extraction.py is run
  Then  it exits with code 0
  And   stdout JSON contains papers list with extraction_status for each

Scenario: run_paper_extraction.py exits 1 when fewer than SRF_MIN_PAPERS are successfully extracted
  Given valid stdin JSON with 2 papers where both fetches fail
  When  scripts/run_paper_extraction.py is run
  Then  it exits with code 1
  And   stderr contains a message indicating insufficient papers

Scenario: srf_forum.yaml contains workspace_setup and paper_extraction as the first two steps
  Given the file workflows/srf_forum.yaml
  When  it is parsed as YAML
  Then  the steps list contains entries named "workspace_setup" and "paper_extraction" in that order
  And   workspace_setup uses run: python scripts/run_workspace_setup.py
  And   paper_extraction uses run: python scripts/run_paper_extraction.py
  And   paper_extraction uses stdin: $workspace_setup.json

Scenario: run_workspace_setup.py writes state.json checkpoint before exiting
  Given valid trigger JSON
  When  scripts/run_workspace_setup.py is run successfully
  Then  state.json exists in the created workspace directory
  And   state.json contains forum_status="workspace_ready"

Scenario: run_paper_extraction.py writes updated state.json checkpoint before exiting
  Given valid stdin from workspace_setup
  When  scripts/run_paper_extraction.py completes successfully
  Then  state.json in the workspace directory contains forum_status="extraction_complete"
  And   state.json contains extracted_paper_count
```

**TDD Notes:** Unit tests for the scripts use `subprocess.run` with crafted stdin JSON and `tmp_path` workspace roots. The `srf_forum.yaml` scenario is a pure YAML parse test — no execution needed. The integration test (`test_lobster_steps.py`) requires `SRF_LLM_PROVIDER` (for the later steps in the YAML, even if not executed here) — skip when absent. The `srf_forum.yaml` created here is a skeleton: it contains all phase steps from the topology document as stubs (with `run: echo placeholder`), with workspace_setup and paper_extraction fully wired. Subsequent epics MODIFY this file to replace stubs with real commands.

---

## Implementation Order

```
Story 4.1 (workspace init + models)
  → Story 4.2 (arXiv fetcher — depends on workspace models for FetchResult path)
    → Story 4.3 (PDF extractor — depends on FetchResult from 4.2)
      → Story 4.4 (scripts + workflow YAML — depends on 4.1, 4.2, 4.3)
```

All four stories are sequential.

---

## Verification Checklist

```bash
# After 4.1
pytest tests/unit/test_workspace_init.py -v

# After 4.2
pytest tests/unit/test_paper_fetcher.py -v

# After 4.3
pytest tests/unit/test_paper_extractor.py -v

# After 4.4
pytest tests/unit/test_run_workspace_setup.py tests/unit/test_run_paper_extraction.py -v
# Verify workflow YAML parses:
python -c "import yaml; w = yaml.safe_load(open('workflows/srf_forum.yaml')); print([s['name'] for s in w['steps']])"
# Expects: ['workspace_setup', 'paper_extraction', ...]

# Full epic suite
pytest tests/unit -v --tb=short
ruff check src/ tests/ scripts/ workflows/

# With live arXiv (use sparingly — rate limit):
pytest tests/integration/test_paper_fetcher_integration.py -v
```

---

## Critical Files

**NEW:**
- `src/srf/workspace/__init__.py`
- `src/srf/workspace/models.py`
- `src/srf/workspace/init.py`
- `src/srf/extraction/__init__.py`
- `src/srf/extraction/fetcher.py`
- `src/srf/extraction/extractor.py`
- `scripts/run_workspace_setup.py`
- `scripts/run_paper_extraction.py`
- `workflows/srf_forum.yaml`
- `tests/unit/test_workspace_init.py`
- `tests/unit/test_paper_fetcher.py`
- `tests/unit/test_paper_extractor.py`
- `tests/unit/test_run_workspace_setup.py`
- `tests/unit/test_run_paper_extraction.py`
- `tests/integration/test_paper_fetcher_integration.py`
- `tests/integration/test_lobster_steps.py`
- `tests/fixtures/papers/` _(minimal programmatic PDF fixtures)_

**MODIFY:**
- `pyproject.toml` _(add `pdfplumber` dependency)_
- `Requirements/progress.md`
