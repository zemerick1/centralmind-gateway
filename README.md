# CentralMind Gateway

**Intelligent LLM-powered event gateway for Aruba Central (and beyond).**

Receives webhooks or on-demand queries → uses your CentralMind MCP server + Grok/Gemini to intelligently process data → posts rich, actionable output to Teams, Slack, custom webhooks, etc.

Built as a **completely separate project** from `central-mind`. Reuses your excellent MCP server via the official MCP Python client — no forking, no duplication of the sandbox/auth/spec logic.

> **Philosophy (same as CentralMind)**  
> LLMs are powerful but must be guided. This gateway gives them tools and clear instructions, keeps everything observable, and defaults to safe (readonly) behavior.  
> You stay in control. The LLM proposes; you (via config + prompts) decide.

---

## Why CentralMind Gateway?

Your `central-mind` MCP server already solves the hardest part: making thousands of Aruba (and Mist, ClearPass, etc.) endpoints usable by LLMs in a safe, token-efficient way.

This gateway adds the **missing orchestration layer**:

- Event-driven triggers (Aruba Central webhooks, custom events)
- On-demand queries (`GET` or `POST /query`)
- LLM "churning" with full access to your MCP tools
- Pluggable outputs (Teams, Slack, HTTP POST, more coming)
- Clean separation of concerns — two distinct, focused projects

---

## Features

- **Webhook receiver** — `POST /webhook/aruba` (and generic `/webhook`)
- **On-demand endpoint** — `POST /query` with prompt + optional context
- **MCP integration** — Spawns and communicates with your `central-mind` server (stdio)
- **Multi-LLM support** — Grok (xAI), Gemini, Claude, OpenAI, local models via LiteLLM
- **Agentic processing** — Simple, controllable ReAct-style loop (no black-box agents)
- **Output destinations** — Teams Incoming Webhooks (with Adaptive Cards), Slack, generic POST, easily extensible
- **Config-driven flows** — Define behavior in `.env` or YAML without changing code
- **Safety first** — Respects `CENTRALMIND_API_MODE=readonly` from your CentralMind setup
- **Docker-ready** — One-command deployment

---

## Quick Start

### 1. Prerequisites

- Python 3.12+
- Your `central-mind` project installed and configured (with a working `.env`)
- Deno (same as CentralMind)
- API keys for at least one LLM (Grok recommended to start)

### 2. Install

```bash
git clone https://github.com/zemerick1/centralmind-gateway.git
cd centralmind-gateway
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Or with `uv` (recommended):

```bash
uv venv
uv pip install -e .
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env — see comments for details
```

**Minimum required in `.env`:**

```env
# Path to your central-mind MCP server command (from your claude_desktop_config.json)
CENTRALMIND_COMMAND="python -m centralmind"

# LLM (Grok example — get key from https://console.x.ai)
LLM_MODEL="xai/grok-3-latest"
XAI_API_KEY="xai-..."

# Or Gemini
# LLM_MODEL="gemini/gemini-2.5-flash"
# GOOGLE_API_KEY="..."

# Output destination (your Teams webhook example)
OUTPUT_WEBHOOK_URL="https://...@7d44fc5a-ab19-4560-ab7d-99875468d1bd/IncomingWebhook/..."

# Optional: Slack webhook
# SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WORKSPACE/TOKEN"

CENTRALMIND_API_MODE=readonly   # or readwrite if you really know what you're doing
```

### 4. Run

```bash
uv run uvicorn app.main:app --reload
```

Or with Docker:

```bash
docker compose up --build
```

Server runs on `http://localhost:8000`

### 5. Test

**On-demand query:**

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Show me the top 5 APs with the most clients right now"}'
```

**Webhook (simulate Aruba alert):**

```bash
curl -X POST http://localhost:8000/webhook/aruba \
  -H "Content-Type: application/json" \
  -d '{"alert_type": "ap_down", "ap_name": "AP-Office-01", "site": "HQ"}'
```

---

## How It Works (Architecture)

```
Webhook / Query
      ↓
      ↓
FastAPI (lifespan starts CentralMind MCP server subprocess)
      ↓
      ↓
Simple Agent Loop (LiteLLM + tool calling)
      ↓
      ↓
      ├─── Tool: aruba.search / aruba.execute   ← calls your CentralMind via MCP
      ├─── Tool: output.post_to_webhook
      ├─── Tool: output.post_to_slack
      └─── ...
      ↓
      ↓
Configured Destinations (Teams, Slack, custom)
```

The agent is **deliberately simple and observable** — you can see every LLM thought, tool call, and result in the logs.

---

## Configuration & Flows

All behavior is driven by environment variables and optional YAML flow definitions in the `flows/` directory.

Example flow (`flows/ap_down.yaml`):

```yaml
name: ap_down_alert
description: "Handle AP offline alerts from Aruba Central"
system_prompt: |
  You are a helpful network operations assistant.
  When an AP goes down, always:
  1. Query CentralMind for current client count and recent events on that AP/site.
  2. Summarize impact in plain English.
  3. Post a rich notification to the primary output channel.
inputs:
  - alert_type
  - ap_name
  - site
outputs:
  - primary: teams
```

The gateway will automatically load and use the most relevant flow based on the incoming event.

---

## Safety & Best Practices

- **Default mode**: `readonly` (inherits from your CentralMind `.env`)
- Never run with `readwrite` in production unless you have strict change-control processes.
- All LLM prompts are logged (redacted tokens).
- Rate limiting and timeout protection on MCP calls.
- Input validation on all endpoints.
- The gateway itself can be protected with API keys or reverse proxy auth.

---

## Project Philosophy (matching CentralMind)

- **Direct and purposeful** — every file has a clear job.
- **User-driven** — you control the prompts, flows, and outputs.
- **No black boxes** — full visibility into what the LLM is doing.
- **Composable** — easy to add new tools, new output channels, new LLMs.
- **Separate concerns** — this gateway never touches your CentralMind code.

---

## Roadmap (Community Welcome)

- [ ] More output channels (Email via SMTP/SendGrid, Discord, PagerDuty)
- [ ] Rich Adaptive Cards for Teams + Slack Block Kit
- [ ] Persistent conversation memory per site/device
- [ ] Web UI for testing queries and viewing logs
- [ ] Support for multiple CentralMind instances (multi-cluster)
- [ ] Prometheus metrics + OpenTelemetry tracing

---

## Contributing

This project follows the same pragmatic, high-signal style as `central-mind`.

Issues and PRs that improve clarity, safety, or add useful output destinations are very welcome.

---

## License

MIT (same as CentralMind)

---

**Built with ❤️ for network engineers who want their LLMs to actually be useful — not just chatty.**

Questions? Open an issue or reach out on X (@zemerick).

---

*This gateway is a companion project to [central-mind](https://github.com/zemerick1/central-mind). They are intentionally kept in separate repositories.*