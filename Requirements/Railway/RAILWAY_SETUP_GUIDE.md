# SRF Railway Setup Guide

Step-by-step instructions for configuring the Railway OpenClaw service to run the Synthetic Research Forum pipeline.

---

## Prerequisites

- Railway account with an OpenClaw service created
- SRF GitHub repo (`SyntheticResearchForum`) pushed and accessible
- Anthropic (or OpenAI) API key

---

## Step 1 — Connect the SRF GitHub Repo

The OpenClaw service needs the SRF codebase as its source so Railway deploys from `railway.toml`.

1. Railway → your OpenClaw service → **Settings** tab
2. Under **Source** → click **Connect Repo**
3. Select the `SyntheticResearchForum` GitHub repo
4. Branch: `main`

Railway will now build from the repo and execute the `startCommand` in `railway.toml`:

```
pip install -e '.[anthropic,openai]' && npm install -g @clawdbot/openclaw @clawdbot/lobster && openclaw start
```

---

## Step 2 — Add a Volume

Workspace artifacts, OpenClaw state, and all SRF forum outputs live on a persistent volume. Without it, everything is lost on restart.

1. Railway → service → **Volumes** tab → **Add Volume**
2. Mount path: `/data`

---

## Step 3 — Enable HTTP Proxy

Required to expose the OpenClaw gateway publicly (for the `/setup` wizard and Claude Desktop MCP connection).

1. Railway → service → **Settings** → **Networking** → **Add HTTP Proxy**
2. Port: `8080`

Railway assigns a public URL: `https://<something>.up.railway.app`

---

## Step 4 — Set Environment Variables

Railway → service → **Variables** tab. Add all variables below.

### Required — service will not start without these

| Variable | Value |
|----------|-------|
| `SETUP_PASSWORD` | A strong password (protects the `/setup` web wizard) |
| `PORT` | `8080` |
| `SRF_LLM_PROVIDER` | `anthropic` (or `openai`) |
| `SRF_LLM_MODEL` | `claude-sonnet-4-6` (or your preferred model) |
| `SRF_LLM_API_KEY` | Your Anthropic / OpenAI API key |

### Required for persistent state

| Variable | Value |
|----------|-------|
| `OPENCLAW_STATE_DIR` | `/data/.openclaw` |
| `OPENCLAW_WORKSPACE_DIR` | `/data/workspace` |

### Recommended — secures MCP and webhook endpoints

| Variable | Value |
|----------|-------|
| `OPENCLAW_GATEWAY_TOKEN` | Generate: `openssl rand -hex 32` |

### Optional — PromptLedger observability (add later)

Both must be set together, or both omitted (graceful degradation — system runs without observability).

| Variable | Value |
|----------|-------|
| `PROMPTLEDGER_API_URL` | Your PromptLedger instance URL |
| `PROMPTLEDGER_API_KEY` | Project-scoped key from `POST /v1/admin/projects` |

### Optional runtime tuning (defaults are fine for initial testing)

| Variable | Default | Description |
|----------|---------|-------------|
| `SRF_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |
| `SRF_ARXIV_DELAY_SECONDS` | `3` | Politeness delay between arXiv fetches |
| `SRF_MIN_PAPERS` | `2` | Minimum papers required to run a forum |
| `SRF_MIN_AGENTS` | `2` | Minimum Paper Agents required for debate |
| `SRF_MAX_PREP_RETRIES` | `3` | LLM call retries during agent preparation |

---

## Step 5 — Deploy and Watch Logs

After setting variables, Railway will auto-redeploy. In the **Deploy Logs**, a healthy startup looks like:

```
Successfully installed srf-0.1.0 anthropic-... openai-...
added N packages — @clawdbot/openclaw, @clawdbot/lobster
OpenClaw Gateway listening on :8080
```

### If `pip: command not found`

The Railway base image for your OpenClaw template does not include Python. Create a `Dockerfile` in the repo root:

```dockerfile
FROM node:20-slim
RUN apt-get update && apt-get install -y python3.11 python3-pip python3.11-venv --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
CMD pip3 install -e '.[anthropic,openai]' \
    && npm install -g @clawdbot/openclaw @clawdbot/lobster \
    && openclaw start
```

Then redeploy. Railway will use the Dockerfile instead of the `startCommand` in `railway.toml`.

### If `openclaw: command not found`

The `npm install -g @clawdbot/openclaw` step failed. Check the deploy logs for the npm error — likely a network issue or incorrect package name. Retry the deploy.

---

## Step 6 — Run the /setup Wizard

Once the service health check passes, open:

```
https://<your-service>.up.railway.app/setup
```

1. Enter your `SETUP_PASSWORD`
2. Choose provider: **Anthropic**, paste your API key
3. Skip Telegram / Discord (not needed for SRF)
4. Click **Run setup**

---

## Step 7 — Run srf_init.py

In the OpenClaw Control UI (`/openclaw`) or via the exec tool, run:

```
python scripts/srf_init.py
```

Expected output on stdout:

```
SRF init complete
```

This confirms:
- Required environment variables are present
- Workspace directories created under `/data/workspace/` (newsletters, candidates, forum, memory)
- `srf` Python package is importable
- PromptLedger prompts registered (if `PROMPTLEDGER_API_URL` is configured) or gracefully skipped

---

## Step 8 — First Integration Test

With the service live and `srf_init.py` confirmed, test the pre-debate pipeline:

### Option A — Newsletter pipeline via exec tool

```
python scripts/parse_newsletter.py --source-path /path/to/newsletter.md --output-dir /data/workspace/newsletters
```

### Option B — Full pipeline via OpenClaw skill (requires Claude Desktop connected via MCP)

Use the `trigger_newsletter_forum` skill, providing a newsletter source path or URL.

### Pipeline phases testable before Epic 6 (debate engine)

| Step | Script | Tests |
|------|--------|-------|
| Workspace setup | `run_workspace_setup.py` | Forum workspace created at `/data/workspace/forum/{id}/` |
| Paper extraction | `run_paper_extraction.py` | PDFs fetched from arXiv, text extracted |
| Agent preparation | `run_preparation.py` | `PreparationArtifact` files written to `preparation/` subdir |
| Debate | `run_debate.py` | **Not yet implemented** — `echo placeholder` in workflow |

---

## Connecting Claude Desktop (MCP)

Once the service is running and `/setup` is complete:

1. Open Claude Desktop → Settings → Developer → Edit Config
2. Add the OpenClaw MCP server:

```json
{
  "mcpServers": {
    "srf": {
      "url": "https://<your-service>.up.railway.app/mcp",
      "headers": {
        "Authorization": "Bearer <OPENCLAW_GATEWAY_TOKEN>"
      }
    }
  }
}
```

3. Restart Claude Desktop
4. The `trigger_newsletter_forum`, `review_forum_debate_format`, and `approve_editorial_review` skills will appear as tools

---

## Verification Checklist

- [ ] GitHub repo connected to Railway service
- [ ] Volume mounted at `/data`
- [ ] HTTP Proxy enabled on port `8080`
- [ ] All required variables set (`SETUP_PASSWORD`, `PORT`, `SRF_LLM_*`, `OPENCLAW_*`)
- [ ] Deploy logs show clean startup (no `pip` or `openclaw` errors)
- [ ] `/setup` wizard completed successfully
- [ ] `python scripts/srf_init.py` returns "SRF init complete"
- [ ] `/health` endpoint responds within 500 ms
- [ ] At least one Lobster pipeline run through `agent_preparation` completes without error
