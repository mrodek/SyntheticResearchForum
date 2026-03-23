# BUG-004 — srf_forum.yaml: invalid initial input reference and relative Python paths

**Status:** Fixed
**Fixed in commit:** 2026-03-22 — see progress_tracker.md

---

## Symptom

Running the `review_forum_debate_format` skill causes the Lobster pipeline to fail immediately at the first step (`workspace_setup`) with a reference error. Subsequent steps would also fail because Python is invoked as a bare `python` command with relative script paths, neither of which resolves correctly from the Lobster gateway working directory.

---

## Root Cause

**PRIMARY — `stdin: $trigger.json` references a non-existent step**

File: `workflows/srf_forum.yaml`, line 9

```yaml
- id: workspace_setup
  command: python scripts/run_workspace_setup.py
  stdin: $trigger.json   # ← BUG: no step named 'trigger' exists
```

In Lobster's step piping syntax, `$stepId.json` means "the JSON output of the step with id `stepId`". There is no step named `trigger`. The trigger JSON (from `validate_and_stage_forum.py`) is the initial workflow input, not a step output. It must be passed via `argsJson` at invocation time and accessed inside steps via `$LOBSTER_ARGS_JSON`.

**SECONDARY — All Python step commands use relative paths**

Files: `workflows/srf_forum.yaml`, lines 8, 14, 23, 31

```yaml
command: python scripts/run_workspace_setup.py   # relative python, relative path
command: python scripts/run_paper_extraction.py  # relative python, relative path
command: python scripts/run_preparation.py        # relative python, relative path
command: python scripts/run_debate_bridge.py      # relative python, relative path
```

Lobster's `cwd` defaults to the OpenClaw gateway working directory, which is not `/data/srf`. Bare `python` resolves to the system Python, not the SRF venv. Relative script paths do not resolve. All Python steps must use absolute paths.

**CONTRIBUTING — SKILL.md uses `input:` parameter which does not exist in the Lobster tool schema**

File: `skills/review_forum_debate_format/SKILL.md`, line 31

```
{"action": "run", "pipeline": "workflows/srf_forum.yaml", "input": <trigger_json>}
```

The Lobster plugin tool schema does not have an `input` parameter. The correct parameter is `argsJson` (a JSON-serialised string). The pipeline path is also relative — it must be absolute.

---

## Impact

- Pipeline cannot start. `workspace_setup` fails immediately.
- Even if the input were somehow resolved, all Python steps would fail with "python not found" or "script not found".

---

## Fix Required

1. **`workflows/srf_forum.yaml`**
   - `workspace_setup`: remove `stdin: $trigger.json`; update command to pipe `$LOBSTER_ARGS_JSON` into the script via shell.
   - `paper_extraction`, `agent_preparation`, `debate`: update to absolute Python and script paths.

2. **`skills/review_forum_debate_format/SKILL.md`**
   - Change `input: <trigger_json>` → `argsJson: <JSON-serialised trigger string>`
   - Change `"pipeline": "workflows/srf_forum.yaml"` → `"pipeline": "/data/srf/workflows/srf_forum.yaml"`
   - Add instruction to serialise the trigger JSON object to a string before passing as `argsJson`.

---

## TDD Plan

Write failing tests first, then implement:

```python
# In tests/unit/test_run_debate_bridge.py

def test_srf_forum_yaml_workspace_setup_does_not_reference_trigger_step():
    # workspace_setup must not reference a non-existent $trigger step
    # $LOBSTER_ARGS_JSON must be used for initial input

def test_srf_forum_yaml_python_steps_use_absolute_paths():
    # All steps calling Python scripts must use /data/venv/bin/python
    # and /data/srf/scripts/ absolute paths
```

---

## Files to Change

- MODIFY: `workflows/srf_forum.yaml`
- MODIFY: `skills/review_forum_debate_format/SKILL.md`
- MODIFY: `tests/unit/test_run_debate_bridge.py` (new test scenarios)
