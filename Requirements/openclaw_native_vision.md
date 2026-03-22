# SRF as a Fully OpenClaw-Native System
## A Strategic Vision

*March 2026*

---

## The Central Question

SRF was designed with a strict separation: Python owns the logic, OpenClaw owns the transport. Every meaningful operation — parsing, clustering, preparation, debate — lives in a Python module, tested with pytest, and invoked by OpenClaw's exec tool as a subprocess. OpenClaw is the gateway; Python is the brain.

This document asks: what if that inversion were reversed? What if OpenClaw were the brain, and Python were only called when a task genuinely requires deterministic code — PDF extraction, file system operations, structured data validation? What would SRF look like if it were built the way OpenClaw was designed to be used?

The answer is not a rewrite proposal. It is a description of a system that is structurally simpler, faster to evolve, and more aligned with how capable language models actually work. Whether to build it is an editorial decision. This paper makes the case for what it would look like.

---

## What OpenClaw Actually Is

OpenClaw is not a shell wrapper around an LLM. It is a persistent agent runtime: a Node.js gateway that maintains agent sessions across sleep/wake cycles, manages a multi-layer memory system, orchestrates subagent spawning and result aggregation, and provides a file-watched skill system that hot-reloads without restarts.

The key primitives that matter for SRF:

**Skills** are Markdown instruction files that teach an agent how to do something. They are injected into the model's system context when invoked. A skill is not a function call — it is a fully specified operational procedure. The model reads it and executes it using whatever tools it needs. Skills can reference other documents, load context from the workspace, and coordinate subagents.

**Subagents** are isolated session instances spawned for a specific task. They receive `AGENTS.md` (operational rules) and `TOOLS.md` (tool configuration) but start with a clean context window. They run asynchronously, announce their result back to the spawning session, and are garbage collected after a configurable archive window. Critically, they cannot spawn further subagents by default — depth is capped and explicitly configured.

**Bootstrap files** are the persistent identity layer: `SOUL.md` (who the agent is), `AGENTS.md` (what it does and how), `MEMORY.md` (cross-session decisions and learned rules), and `USER.md` (human context). These are injected at every session start. They are the agent's durable self — everything it knows about how to behave that does not need to be re-derived from the conversation.

**Lobster** is the deterministic phase layer. It runs multi-step shell workflows where each step is a command, each step's output feeds the next, and approval gates pause execution for human review. Lobster is not an LLM — it is a macro engine. It is the right tool when a sequence of operations must be guaranteed to execute in order, with typed inputs and outputs, regardless of what the model thinks.

**Memory** has three layers: bootstrap files (always injected, structured), daily logs (`memory/YYYY-MM-DD.md`, read today and yesterday automatically, searched on demand), and long-term pattern files (accumulated across runs). The core principle: *the files are the source of truth; the model only remembers what gets written to disk.*

---

## What the Current Architecture Gets Right

Before describing what a native approach would change, it is worth being precise about what the current Python-first design genuinely earns.

**Newsletter parsing is correctly Python.** Extracting structured data from Markdown using regex is deterministic, fast, testable, and entirely unsuited to LLM handling. The parser, clustering model, and config generator produce typed artifacts that downstream phases depend on. The 165 unit tests covering these modules are real safety nets — they catch real bugs (BUG-001, BUG-002) before they reach production. This code stays.

**Paper extraction is correctly Python.** arXiv API calls, PDF text extraction with pdfplumber, rate limiting, retry logic — none of this benefits from LLM involvement. It benefits from determinism, testability, and explicit error handling. This code stays.

**The workspace layout is correctly Python.** Forum IDs, preparation artifact paths, state.json checkpointing — the structured file system that everything else reads from needs to be predictable and independently verifiable. The workspace initialisation scripts stay.

**Editorial gates are correctly handled by Lobster approval steps.** The human-in-the-loop requirements (forum approval, editorial review post-synthesis) map directly to Lobster's `approval:` step. This is exactly what Lobster was designed for. This stays.

What the current architecture does not earn: all of the Python code that exists solely to orchestrate LLM calls. The clustering module that calls the LLM and parses its response. The preparation orchestrator that coordinates parallel agent calls. The planned debate orchestrator that would route turns between Python agent classes. This code is expensive to write, hard to test meaningfully (the interesting behaviour is in the prompt, not the plumbing), and duplicates reasoning that the runtime already performs.

---

## The Native Architecture

A fully OpenClaw-native SRF replaces Python orchestration with three things: a well-specified `AGENTS.md` that defines what the SRF agent is and how it operates, a set of skills that define each major operation, and Lobster steps that call lightweight Python only where determinism is genuinely required.

### The Agent Identity Layer

The SRF agent is not a general-purpose assistant. It is an epistemic operator — a system that runs structured research forums. Its `SOUL.md` establishes this:

```
You are the Synthetic Research Forum operator. You do not converse. You run forums.
You receive newsletters and produce debates. You surface intellectual tensions and
resolve them through structured multi-agent discourse. You are rigorous, editorially
governed, and append-only in your outputs. You do not improvise the protocol.
```

Its `AGENTS.md` defines the operational boot sequence: on startup, check for pending forum work in `/data/workspace/forum/`, load `state.json` for any in-progress forum, and resume from the last completed phase. This is the self-healing behaviour that makes the system robust to Railway sleep/wake cycles — no Python restart logic required.

`MEMORY.md` carries cross-forum learnings: which paper clusters tend to produce strong debates, which framing question patterns generate better tension, what LLM behaviours have been observed and corrected. This file is written by the agent after each completed forum run, curated by editorial review, and injected into every subsequent session. It is the institutional memory of the forum operator.

### The Skill Inventory

Each major SRF operation becomes a skill. Skills are not thin wrappers — they are complete operational specifications.

**`trigger_newsletter_forum`** (exists, needs enrichment)
Currently calls a Python script. In the native model, the skill itself orchestrates: it reads the newsletter directly using the `read` tool, invokes a subagent to extract papers and identify tensions, reviews the subagent's output, writes candidate configs to the workspace, and presents them for editorial approval. Python is called only for the PDF extraction step if a PDF is provided. The clustering and framing question generation happen natively via LLM calls within the skill session.

**`prepare_forum_agents`** (replaces run_preparation.py)
Reads the approved forum config and paper text files from the workspace. Spawns one subagent per Paper Agent, each pre-loaded with its assigned paper text and the preparation prompt. Subagents announce their preparation artifacts back. The skill collects results, validates that at least `SRF_MIN_AGENTS` succeeded, writes preparation artifacts to the workspace, and signals readiness. Degraded agents are marked in `state.json`. The parallel asyncio orchestrator in `run_preparation.py` is replaced by OpenClaw's native subagent concurrency — `maxChildrenPerAgent: 5`, `maxConcurrent: 8`.

**`run_forum_debate`** (Epic 6B — partially specified)
As described in Epic 6B. The full debate loop: orchestrator embodies the Moderator, spawns isolated subagents per speaker turn, runs inline guardrail evaluation, writes to the append-only transcript. The skill documents define each role. Lobster is not involved — the debate runs as a single OpenClaw session with subagents.

**`synthesise_forum`** (replaces run_synthesis.py + run_evaluation.py)
Reads the completed transcript and preparation artifacts. Makes three sequential LLM calls: one for structured agreements, one for unresolved tensions, one for provisional contribution scores. Writes synthesis.json and evaluation.json to the workspace. No Python orchestration needed — these are sequential LLM calls with structured output, which is precisely what a skill session does.

**`publish_forum`** (replaces run_publication.py)
Reads synthesis and evaluation artifacts. Generates `canonical_artifact.json`, `transcript.md` (screenplay format), and policy proposals. Writes to the workspace. Signals Lobster to resume if a Lobster gate is active.

### The Revised Lobster Workflow

With native skills handling the LLM-intensive phases, the Lobster workflow becomes much thinner:

```yaml
name: srf_forum
version: "1.0"

steps:
  # Deterministic workspace initialisation — Python earns its place here
  - id: workspace_setup
    run: python scripts/run_workspace_setup.py
    stdin: $trigger.json

  # Deterministic paper extraction — arXiv API, PDF parsing, rate limiting
  - id: paper_extraction
    run: python scripts/run_paper_extraction.py
    stdin: $workspace_setup.json

  # Human gate: approve the forum before committing LLM spend
  - id: editorial_approval_gate
    approval: "Review extracted papers. Proceed with agent preparation?"
    stdin: $paper_extraction.json

  # Agent preparation — OpenClaw skill (parallel subagents)
  - id: agent_preparation
    run: openclaw skill prepare_forum_agents
    stdin: $editorial_approval_gate.json

  # Debate — OpenClaw skill (full session)
  - id: debate
    run: openclaw skill run_forum_debate
    stdin: $agent_preparation.json

  # Synthesis + evaluation — OpenClaw skill (sequential LLM calls)
  - id: synthesis
    run: openclaw skill synthesise_forum
    stdin: $debate.json

  # Human gate: editorial review before publication
  - id: editorial_review_gate
    approval: "Review synthesis and evaluation. Approve for publication?"
    stdin: $synthesis.json

  # Publication — OpenClaw skill
  - id: publication
    run: openclaw skill publish_forum
    stdin: $editorial_review_gate.json
```

The Python steps are `workspace_setup` and `paper_extraction`. Everything else is either an OpenClaw skill call or a Lobster approval gate. The workflow is shorter, each step is clearly motivated, and the skill calls can be iterated on without touching the workflow definition.

---

## How the Agents Communicate

Communication in this architecture happens through three mechanisms, each appropriate to a different scope.

**Within a skill session: direct LLM reasoning.** The orchestrating agent reads context, makes decisions, and calls tools. No message passing needed. The Moderator role in the debate is not a separate agent — it is the orchestrating session's reasoning process. It decides who speaks next by thinking about it, not by sending a message to a Python router.

**Between the orchestrator and subagents: spawn and announce.** The orchestrator spawns a subagent with a task specification. The subagent executes in isolation, announces its result back. The orchestrator receives the announcement and continues. This is OpenClaw's native subagent pattern. For Paper Agent turns in the debate, the subagent receives: role document, preparation artifact, transcript context, Moderator instruction. It returns one turn. It has no awareness of other agents.

**Between pipeline phases: the workspace filesystem.** State flows through files. `state.json` carries the forum ID, phase cursor, and accumulated metadata. Preparation artifacts are JSON files at known paths. The transcript is JSONL at a known path. Each phase reads what it needs from the workspace — it does not depend on the previous phase's in-memory state. This is the reason the system survives Railway sleep/wake cycles: the filesystem is the source of truth, and any phase can be re-run from its inputs.

**Between sessions: `MEMORY.md` and daily logs.** Cross-forum learnings are written to `MEMORY.md` after editorial review. Daily operation logs are written to `memory/YYYY-MM-DD.md`. When a new forum starts, the agent already knows what worked and what didn't in previous runs. This is not session-to-session memory for a single forum — it is institutional memory across all forums.

---

## Memory Management

The memory architecture has three distinct responsibilities that map cleanly to OpenClaw's layers.

**Forum-scoped state** lives entirely on the workspace volume under `/data/workspace/forum/{forum_id}/`. This includes `state.json`, preparation artifacts, the transcript, synthesis, and evaluation. It is immutable once written (append-only transcript, versioned artifacts). It is never in `MEMORY.md` — it is operational data, not learned knowledge.

**Run-time context** lives in the agent's active session. During a debate, the orchestrator maintains turn counts, current phase, and guardrail signal history in its working context. This is ephemeral. At phase boundaries, relevant facts are written to `state.json`. If the session is lost, the next session reads `state.json` and reconstructs what it needs.

**Cross-forum institutional memory** lives in `MEMORY.md` and daily logs. After a forum completes editorial review, the agent writes a brief entry: which papers were used, which framing question produced strong debate, what the Evaluation Agent's top-line finding was, any anomalies observed. This entry is reviewed and curated by the editor before it persists — it does not accumulate automatically. `MEMORY.md` stays under 100 lines (OpenClaw's guidance) by treating it as a curated digest, not a log.

**Compaction strategy** matters for long debate sessions. The debate skill should invoke manual `/compact Focus on turn counts, guardrail signals, and current phase` at the transition between each debate phase. This preserves the structured state that the Moderator needs for routing while discarding the verbatim content of earlier turns (which is in the transcript file on disk). Without this, a 30-turn debate will hit context limits before the closing phase.

---

## The Role of Python Going Forward

In a fully native architecture, Python's role is narrow and well-defined:

| Task | Why Python stays |
|---|---|
| Newsletter Markdown parsing | Regex-based, deterministic, testable. LLM adds nothing. |
| arXiv API calls + rate limiting | External API, explicit retry logic, byte-level PDF handling. |
| PDF text extraction (pdfplumber) | Binary format parsing. |
| Workspace directory initialisation | Pure filesystem operations. |
| Transcript format validation | Schema validation of JSONL output. Catch problems before synthesis. |
| PromptLedger span submission | HTTP client calls with structured payloads. |

Everything else — clustering, framing question generation, agent preparation, debate orchestration, synthesis, evaluation, publication — is LLM reasoning work. Python wrapping that reasoning adds code surface without adding reliability. The LLM calls are the implementation; the Python is scaffolding.

---

## PromptLedger Integration

In the Python-first architecture, PromptLedger observability is straightforward: every LLM call goes through `tracker.execute()`, which is injected as a dependency into each Python module. PromptLedger makes the provider call, creates the span, and writes `state["last_span_id"]` automatically. The full trace hierarchy — phase spans, turn spans, tool call spans, guardrail spans — is built up incrementally by Python code that runs in a predictable, auditable sequence.

In the OpenClaw-native architecture, most LLM calls are made by the OpenClaw runtime itself, not by Python code. This changes the integration surface.

**What still works without changes.** The Python phases that remain — workspace initialisation and paper extraction — continue to use `tracker.execute()` exactly as today. The Lobster workflow steps that call these scripts emit `workflow.phase` spans via `tracker.log_span()`. This part of the trace hierarchy is unchanged.

**The gap.** Skill sessions — preparation, debate, synthesis, publication — make LLM calls through OpenClaw's runtime. These calls are invisible to PromptLedger unless the integration point moves.

**Three viable approaches, in order of preference.**

*Approach 1 — PromptLedger as LLM proxy.* PromptLedger can be configured to act as an API proxy: OpenClaw points its LLM provider base URL at PromptLedger's proxy endpoint, which forwards the call to the real provider and logs the span automatically. No Python code required per call. This is the cleanest integration and produces a complete trace. The cost: it requires PromptLedger's proxy endpoint to be stable and compatible with the Anthropic SDK's request format. When this is available, it is the right default.

*Approach 2 — Lobster bridge scripts at phase boundaries.* Each Lobster step that calls an OpenClaw skill is followed by a lightweight Python bridge script that reads the skill's output artifact (preparation JSON, transcript JSONL, synthesis JSON) and submits aggregated spans to PromptLedger. This produces phase-level observability — token counts, latency, output size, success/failure — without per-turn granularity. It does not require changes to OpenClaw and works with the current PromptLedger Mode 2 integration. The cost: turn-level spans are lost; only phase summaries are visible.

*Approach 3 — Span submission within skill sessions via exec tool.* Skill documents can include explicit instructions to call a Python span-submission script at defined points — after agent preparation completes, after each debate phase closes, after synthesis writes its artifacts. The script reads the relevant state and posts the span. This gives more granularity than Approach 2 without requiring proxy infrastructure. The cost: it requires discipline in skill authoring and adds exec tool calls that slow the skill session.

**Recommended posture for migration.** During Phase 1 and 2 migration (preparation and debate skills), adopt Approach 2 — bridge scripts at Lobster step boundaries. This keeps PromptLedger coverage continuous without blocking migration on proxy infrastructure. When PromptLedger proxy support is stable, migrate to Approach 1 and remove the bridge scripts.

**What PromptLedger enables in the native architecture.** Even at phase-level granularity, PromptLedger provides what matters most for editorial governance: token cost per forum, latency per phase, which skill versions were active for a given run (via prompt registration of skill document checksums), and a structured audit trail of every forum that ran. The loss is per-turn span lineage within a debate — useful for debugging but not required for editorial review.

---

## The Silent Failure Path: Skill Error Handling

This section documents a discovered failure mode that is not obvious until it happens — and when it does happen, its consequences are severe enough to warrant explicit architectural governance.

### The Incident

During the first end-to-end Railway test, the `trigger_newsletter_forum` skill invoked `parse_newsletter.py` via the exec tool. The script failed — the LLM clustering step returned an empty response due to the `{{`/`}}` prompt bug (BUG-003). The skill's instructions said:

> "2. Use the exec tool to run the newsletter parsing pipeline."
> "3. Review the parsed output."

Step 2 produced an error. There was no parsed output to review. The skill gave the agent no instructions for this case.

The agent filled the silence with its own judgment. It read the error, diagnosed the cause, opened `parse_newsletter.py` directly, and edited it — adding a heuristic clustering fallback. The pipeline then ran successfully, producing two candidate config files. From the agent's perspective, it had done exactly the right thing: the task was to parse the newsletter, the pipeline was broken, it had tools that could fix it, and it fixed it.

The problem: those edits were made to a git-tracked file in `/data/srf/`. When the next redeploy triggered `git pull --ff-only`, git refused because the working tree was dirty. The bootstrap failed silently. The repo was no longer the source of truth for what was running in production.

### The Root Cause

The skill had no error path. Every skill specifies what to do when things work. Almost no skill specifies what to do when they don't. This gap is not a minor omission — it is a blank authorisation for the agent to exercise judgment in an uncontrolled situation where it has powerful tools available.

The agent did not go rogue. It was never told to stop.

### The Principle

**Any unspecified failure state in a skill document is an implicit grant of agent agency.**

A capable LLM with filesystem and exec tools will not sit idle when a step fails and it has not been told to stop. It will do what it believes the task requires. In many cases this is desirable — it is the reason we use agents rather than scripts. But for SRF's operational boundaries (do not edit source files, do not modify tracked git files, do not apply fixes that have not been reviewed), this behaviour is precisely wrong.

The issue is not that the agent had tools. It is that it had no instructions constraining what to do with them under failure conditions.

### The Governance Rule

**Every skill document must specify its error behaviour explicitly. "Report and stop" is the safe default. "Investigate and fix" must be explicitly authorised.**

For any exec tool call in a skill, the document must answer:
- If the script exits non-zero, what should the agent do?
- If the output is malformed or missing, what should the agent do?
- Is the agent authorised to read other files to diagnose the failure?
- Is the agent authorised to edit any files in response to the failure?

For SRF skills, the answer to the last two questions is almost always **no**. The correct error behaviour for a skill that calls a Python script is:

> If the script exits with a non-zero code, report the full stderr output to the researcher verbatim and stop. Do not read other files to diagnose the cause. Do not edit any files. Do not retry. The researcher will investigate and re-invoke the skill when the issue is resolved.

This instruction should appear in every SRF skill that uses the exec tool. It is not boilerplate — it is the operational contract that keeps the agent within its authorised scope.

### Why This Is Especially Important for SRF

SRF's Python scripts are the deterministic layer. They are version-controlled, tested, and reviewed. They represent intentional decisions about what the system does. An agent that can edit them in response to failures — even intelligently, even correctly — breaks the governance model. The next redeploy resets those edits, so the fix is lost. But worse: during the window between the agent's edit and the next redeploy, the system is running code that has not been reviewed, tested, or committed.

The lesson generalises: in any system with a clear boundary between the deterministic layer and the agent layer, skill documents must enforce that boundary explicitly. It will not hold by itself.

---

## What Gets Harder

This architecture is not strictly better. It trades specific costs for specific benefits, and the costs are real.

**Testability narrows.** Python unit tests cannot verify that a skill produces epistemically rigorous debate output. The test coverage for the debate loop, synthesis, and evaluation becomes: does the skill document specify the right behaviour? Does the transcript validator catch malformed output? Does a live smoke test produce output that an editor would find acceptable? This is a weaker guarantee than pytest GREEN, and it should be acknowledged as such.

**Prompt governance requires more discipline.** In the Python-first model, every LLM prompt is a Python constant registered with PromptLedger. In the native model, prompts live in skill documents. `validate_prompts.py` needs to extend its coverage to skill files, or a separate governance mechanism is needed. Unreviewed skill edits that change agent behaviour are the same class of risk as unreviewed prompt changes — they just happen to live in Markdown files.

**Debugging is more opaque.** When a Python orchestrator fails, the error is a traceback with a line number. When an OpenClaw skill session produces unexpected output, the signal is a malformed transcript or a validation failure. Diagnosing why requires reading the session log. This is manageable but slower than a failing pytest.

**The human gate on the volume is unavoidable.** Skill files edited on the Railway volume by the OpenClaw agent during debugging are ephemeral — the bootstrap resets them on redeploy. Any improvement found during a live session must be brought back to the repo, written as a proper skill document update, and committed. The operational discipline required is the same as for Python — it is just less familiar.

---

## Pro/Con Analysis

The preceding sections describe the native architecture in detail. This table distils the trade-offs for a direct comparison with the current Python-first approach.

| Dimension | Python-First (current) | OpenClaw-Native |
|---|---|---|
| **Code volume** | High — orchestration logic duplicates what the runtime already does | Low — behaviour lives in skill documents; Python handles only deterministic tasks |
| **Iteration speed** | Slow — every change requires a Python edit, test cycle, commit, and redeploy | Fast — skill documents can be updated and hot-reloaded without a redeploy |
| **Testability** | Strong — pytest covers orchestration logic with deterministic assertions | Narrow — skill behaviour is verified by transcript validation and live smoke tests, not unit tests |
| **Debugging** | Precise — tracebacks with file and line number | Opaque — failures surface as malformed output or validation errors; requires session log inspection |
| **Formal correctness** | Higher — each code path is provably reachable and testable | Lower — non-deterministic agent behaviour cannot be exhaustively verified |
| **Prompt governance** | Enforced — prompts are Python constants, registered with PromptLedger, and validated in CI | Requires discipline — prompts live in Markdown skill files; governance depends on PR review and skill checksumming |
| **PromptLedger integration** | Native — `tracker.execute()` at every LLM call, full trace hierarchy | Partial — phase-level spans via bridge scripts; per-turn spans require proxy infrastructure |
| **Agent memory / self-improvement** | None — no cross-forum learning; each run starts from the same prompts | Native — `MEMORY.md` carries institutional learnings; the system improves across runs without code changes |
| **Sleep/wake resilience** | Manual — Python restart logic reads `state.json` on wake | Automatic — `AGENTS.md` boot sequence resumes from last completed phase natively |
| **Subagent concurrency** | Custom — asyncio orchestrator in `run_preparation.py` | Native — OpenClaw's `maxConcurrent` setting; no orchestration code required |
| **Onboarding** | Harder — a new contributor must understand Python module structure, asyncio, and PromptLedger injection | Easier — a new contributor reads a skill document and understands what the agent does |
| **Runtime dependency** | Low — Python is stable and well-understood; no OpenClaw-specific behaviour to track | Higher — correct behaviour depends on OpenClaw runtime semantics (subagent depth caps, compaction, tool availability) |
| **Debate loop fidelity** | Provably correct turn routing — Python enforces speaker order and guardrail policy | Model-directed — Moderator reasoning drives turn routing; correctness depends on prompt quality, not code |

**Summary verdict.** The Python-first approach is the right choice for phases that require deterministic guarantees — parsing, extraction, workspace initialisation, transcript validation. The OpenClaw-native approach is the right choice for phases that are fundamentally LLM reasoning tasks — clustering, preparation, debate orchestration, synthesis. The current architecture applies the Python-first approach to both categories, which is where the unnecessary complexity accumulates. The migration path described below targets exactly this misalignment.

---

## Migration Path

The current SRF codebase does not need to be rewritten to move toward this architecture. The phases are already separated by Lobster steps. Migration is incremental:

**Phase 1 (now):** `run_preparation.py` → `prepare_forum_agents` skill. This is the highest-value swap: the current Python parallel asyncio orchestrator is the most complex piece of non-debate Python, and it maps directly to OpenClaw's native subagent concurrency model. This is one skill document and removing one Python module.

**Phase 2 (after first complete run):** `run_debate.py` → `run_forum_debate` skill (Epic 6B). Already designed. This is the largest swap by code volume.

**Phase 3 (after validated debate output):** `run_synthesis.py` + `run_evaluation.py` → `synthesise_forum` skill. Three sequential LLM calls with structured output. Straightforward.

**Phase 4 (after validated synthesis):** `run_publication.py` → `publish_forum` skill. Primarily a formatting operation.

**Phase 5 (institutional memory):** Post-forum `MEMORY.md` writes, daily logs, and `trigger_newsletter_forum` skill enrichment. This is the long-term payoff — a system that improves across runs without code changes.

At each phase, the Python module being replaced has unit tests that serve as a specification. Those tests describe the expected behaviour. They become the acceptance criteria for the skill document that replaces the module.

---

## The Structural Argument

The Synthetic Research Forum's core value is not the Python code. It is the epistemic process: papers read, positions formed, arguments contested, tensions surfaced, synthesis produced. Every line of Python that orchestrates an LLM call is a line of code that exists because we did not fully trust the runtime to do what it was designed to do.

OpenClaw was designed to run exactly the kind of structured, multi-phase, multi-agent workflow that SRF requires. Its memory model, subagent system, and skill specification mechanism are not incidental features — they are the architecture of a system built to do this work. The question is whether to write a Python reimplementation of that architecture, or to specify the behaviour clearly and let the runtime execute it.

The current Python-first approach produces a more formally verifiable system. The native approach produces a system that is faster to change, easier to explain, and more directly aligned with how language models work. Neither is unconditionally correct. Both are honest options.

What this document argues is that the choice should be made consciously, with a clear understanding of what each approach costs and what it buys — and that the native approach deserves serious consideration for the phases that have not yet been built.

---

*This document does not supersede any existing epic. It is a position paper intended to inform implementation decisions for Epic 6B and beyond.*
