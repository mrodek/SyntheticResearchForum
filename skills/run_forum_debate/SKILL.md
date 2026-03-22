---
name: run_forum_debate
description: Run a complete multi-agent Synthetic Research Forum debate. Orchestrates the Moderator, Paper Agents, Challenger, and Guardrail through a structured five-phase debate loop, writing an append-only JSONL transcript to the forum workspace.
---

# run_forum_debate

Use this skill when the agent preparation phase has completed and `debate_context.json` is present in the forum workspace. This skill runs the full debate loop from opening to closing, producing a validated transcript for the synthesis phase.

---

## Parameters

- **context_path** (required): Absolute path to `debate_context.json` in the forum workspace.

---

## Inputs

Load the following before beginning the debate loop:

1. Read `debate_context.json` from `context_path`. This document contains everything needed to run the debate:
   - `forum_id`, `topic`, `framing_question`, `tension_axis`
   - `agents` — roster with `agent_id`, `role`, `status`, and `artifact_path` for ok agents
   - `limits` — `max_total_turns`, `max_turns_per_agent`, `max_rounds`
   - `transcript_path` — absolute path to `transcript.jsonl`
   - `closed_sentinel` — always `"DEBATE_CLOSED"`

2. Load role documents into context:
   - `MODERATOR.md` — Moderator role specification
   - `PAPER_AGENT.md` — Paper Agent role specification
   - `CHALLENGER.md` — Challenger role specification
   - `GUARDRAIL.md` — Guardrail evaluation specification

3. For each agent with `status: "ok"`, read their preparation artifact from `artifact_path`.

4. Print a brief confirmation: forum_id, framing question, agent count, transcript path.

---

## Debate Phases

The Moderator sequences the debate through five phases. Each turn's `phase` field must reflect the current phase. The Moderator signals phase transitions in its routing decisions.

| Phase | Moderator goal | Transitions when |
|---|---|---|
| `opening` | Each agent states its claimed position; no cross-examination | All agents have spoken once |
| `position` | Each agent develops its core argument in depth | Each agent has spoken twice total |
| `challenge` | Challenger applies structured pressure; agents defend | Challenger has spoken at least twice |
| `discussion` | Open cross-examination; route to maximise intellectual tension | Moderator judges exhaustion or limit reached |
| `closing` | Each agent states what changed and what did not | All agents have given a closing statement |

The Moderator is not required to complete every phase. If limits are reached, close at whatever phase is current.

---

## Turn Protocol

Execute this loop until a close condition is met:

**MODERATOR TURN:**

Spawn a subagent with:
- System: contents of `MODERATOR.md`
- Context: current transcript (last 60,000 characters), agent roster with turn counts and statuses, guardrail signal history, forced_routing flag and reason if active, framing question, current phase, current turn count vs limits

The subagent must return one of:
- Routing decision: `{"next_speaker": "<agent_id>", "instruction": "<guidance for this turn>", "phase": "<current_phase>"}`
- Close decision: `{"action": "close", "reason": "<why closing>"}`

Write the Moderator routing decision as a transcript line (`role: "moderator"`). The `content` field contains the instruction given to the next speaker.

If the Moderator returns a close decision, write the `DEBATE_CLOSED` sentinel and exit the loop.

**SPEAKER TURN:**

Identify the agent from `next_speaker`. If the agent has `status: "degraded"`, skip them, log a warning line to the transcript, and force a Moderator re-route on the next iteration.

Spawn a subagent with:
- System: contents of the agent's role document (`PAPER_AGENT.md` or `CHALLENGER.md`) plus their preparation artifact JSON
- User: framing question, current transcript context (truncated to 60,000 characters), Moderator's instruction for this turn

The subagent returns plain prose — the turn content. No JSON wrapping required from the speaker.

Write the turn to `transcript.jsonl` (see Transcript Format below).

**GUARDRAIL CHECK (inline — not a subagent):**

After writing each speaker turn, make a direct LLM call:
- Prompt: contents of `GUARDRAIL.md` + turn content + speaker role + framing question
- Response must be JSON: `{"signal": "ok"|"warning"|"critical", "reason": "<explanation>"}`

If `"critical"`: set `forced_routing = true`, attach reason to next Moderator context. Write the guardrail result to the turn's `metadata.guardrail_signal` field.
If `"warning"`: log in the turn's metadata, continue normally.
If `"ok"`: continue.

**LIMIT CHECK:**

After each speaker turn:
- If `total_turns >= max_total_turns`: close with `reason: "max_total_turns_reached"`
- If any agent's `turn_count >= max_turns_per_agent`: exclude from future speaker routing
- If `round_count >= max_rounds`: close with `reason: "max_rounds_reached"`

---

## Hard Limits

Hard limits are not suggestions. They are enforced unconditionally:

- When `max_total_turns` is reached, the debate **must** close regardless of Moderator preference. Write the sentinel immediately.
- Agents with `status: "degraded"` are excluded from the speaker queue at all times. Never route to a degraded agent.
- `max_turns_per_agent` excludes an agent from future routing once reached. It does not close the debate.
- These limits are read from `debate_context.json` and are not overrideable during the session.

---

## Transcript Format

Every speaker turn appended to `transcript.jsonl`:

```json
{
  "turn_id": "t-0001",
  "speaker_id": "paper-agent-1",
  "role": "paper_agent",
  "phase": "position",
  "content": "...",
  "timestamp": "2026-03-22T10:00:00Z",
  "metadata": {
    "guardrail_signal": "ok",
    "guardrail_reason": "",
    "moderator_instruction": "Defend your position on retrieval..."
  }
}
```

Moderator routing turns use `role: "moderator"`. The `content` field contains the instruction given to the next speaker.

The transcript is **append-only**. Never overwrite or truncate a line that has been written. There is no concurrent writer — append-only is enforced by instruction, not file locking.

---

## Closing Protocol

When the debate closes (Moderator decision or limit reached), write the final sentinel line:

```json
{"type": "DEBATE_CLOSED", "reason": "max_total_turns_reached", "total_turns": 30, "timestamp": "2026-03-22T10:30:00Z"}
```

The `"reason"` field must be populated. Valid reasons: `"moderator_closed"`, `"max_total_turns_reached"`, `"max_rounds_reached"`, `"error"`.

After writing the sentinel, print a brief summary to the session: forum_id, total turns, close reason, transcript path.

---

## Compaction

At the transition between `position` and `challenge` phases, and again between `challenge` and `discussion`, invoke `/compact Focus on turn counts per agent, guardrail signals, current phase, and forced_routing status`. This preserves the structured state the Moderator needs for routing while discarding verbatim content of earlier turns that is already written to the transcript file on disk.

---

## Error Handling

**This skill must never edit any file under `/data/srf/`.** That directory is a git-tracked deployment clone. Editing it in response to errors bypasses version control and code review, and causes `git pull` to fail on the next redeploy. All source-level fixes must be made in the repository by the developer and redeployed.

| Failure | Required action |
|---|---|
| `debate_context.json` missing or not valid JSON | Report the path and error to the researcher verbatim. Write nothing to the transcript. Stop immediately. |
| A preparation artifact file listed in `debate_context.json` cannot be read | Report the agent_id and artifact_path. Stop immediately. |
| Subagent returns empty output or output that cannot be parsed | Report the agent's role, turn number, and the raw output received. Write a `{"type": "DEBATE_ERROR", "reason": "subagent_empty_output", "turn": <n>}` line to the transcript. Stop. |
| Moderator subagent returns output that is not valid routing JSON | Report the raw output. Do not guess at the intended routing decision. Stop. |
| Transcript write fails (file I/O error) | Report the error and the turn that could not be written. Stop. The partial transcript remains on disk for inspection. |
| Any unexpected exception during the debate loop | Write a `DEBATE_ERROR` sentinel to the transcript if possible, then report and stop. |

In all error cases: report and stop. Do not attempt to diagnose root causes by reading other files. Do not retry failed subagent calls. Do not modify any source files.
