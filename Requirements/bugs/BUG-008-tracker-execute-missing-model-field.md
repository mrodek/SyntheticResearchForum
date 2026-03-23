# BUG-008 — tracker.execute() missing model field causes PL 500

**Symptom:**
`run_preparation.py` fails in production with HTTP 500 from PromptLedger:
```
KeyError: 'model'
Root cause: The SRF Application is sending requests to /v1/executions/run without
including a model field in the request body. The API expects this field at line 240
in execution.py.
```

**Root Cause:**

**PRIMARY — `src/srf/agents/preparation.py` all three `tracker.execute()` call sites (lines ~169, ~238, ~302):**
```python
result = await tracker.execute(
    prompt_name="agent.paper_preparation",
    messages=messages,
    mode="mode2",
    state=state,
    agent_id=assignment.agent_id,
    # MISSING: model={"provider": "...", "model_name": "..."}
)
```
The PromptLedger `/v1/executions/run` API requires a `model` field:
```json
{"provider": "anthropic", "model_name": "claude-sonnet-4-6"}
```
`config.llm_provider` and `config.llm_model` are already available at all three call sites
(they're needed for the tracker=None fallback path), but are not passed to `execute()`.

**Impact:**
- All three agent preparation calls fail with PL 500 when `tracker is not None`
- `run_preparation.py` exits non-zero, halting the Lobster pipeline
- Affects every forum run on Railway where PromptLedger is configured

**Fix Required:**
Add `model={"provider": config.llm_provider, "model_name": config.llm_model}` to all three
`tracker.execute()` calls in `preparation.py`.

**Risks:**
- If the SDK's `execute()` does not support a `model` kwarg, a `TypeError` would be raised.
  In that case, the client constructor may need `provider` and `model_name` kwargs instead.
- Low risk — `config` is already available at each call site.

**TDD Plan:**

1. Add to `tests/unit/test_paper_agent_preparation.py` (or equivalent):
   - Scenario: `tracker.execute()` is called with `model` dict containing `provider` and `model_name`
   - Verify `tracker.execute.call_args` includes `model={"provider": ..., "model_name": ...}`
2. Same for moderator and challenger preparation tests
3. Run → RED
4. Add `model={"provider": config.llm_provider, "model_name": config.llm_model}` to all three call sites
5. Run → GREEN

**Files to Change:**
- `src/srf/agents/preparation.py` — add `model` kwarg to three `tracker.execute()` calls
- `tests/unit/test_paper_agent_preparation.py` — add assertion on model kwarg
- `tests/unit/test_moderator_challenger_preparation.py` — add assertion on model kwarg

**Fixed in commit:** 0c778a4

**Resolution note (from PL team):**
The SDK's `execute()` signature is `model: Optional[str]` — the intended interface is a plain
string (the model name), not a dict. We pass a dict:
```python
model={"provider": config.llm_provider, "model_name": config.llm_model}
```
This works because Python doesn't enforce type hints and the dict passes through to the request
body verbatim. It is undocumented behavior in the SDK — it relies on the raw API form, not
the SDK's intended `Optional[str]` interface.

The PL server was also patched to handle absent/string model gracefully. Both fixes are
complementary: SRF always passes model explicitly (won't hit the bug even on old server code),
and the PL server no longer 500s if model is absent or in string form.

**Future cleanup:** Switch to the string form matching the SDK's intended interface:
```python
model=config.llm_model  # e.g., "claude-sonnet-4-6"
```
Not urgent — the dict form works and both layers of protection are now in place.
