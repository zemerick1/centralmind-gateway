# CentralMind Gateway

Minimal, generic webhook event processor using your **central-mind** MCP server.

## Philosophy

- Webhook-only (no interactive API)
- Fully generic core (no vendor-specific logic)
- Dynamic tool discovery from central-mind
- Very small codebase (3 main files)
- Logging is the default output

## Files

- `main.py` — FastAPI app + processing
- `config.py` — Settings
- `mcp_client.py` — MCP connection with dynamic `search_*` / `execute_*` discovery

## Quick Start

```bash
git clone https://github.com/zemerick1/centralmind-gateway.git
cd centralmind-gateway
uv venv && source .venv/bin/activate
uv pip install -e .

cp .env.example .env   # edit with your keys and URLs
uvicorn main:app --reload
```

Send a webhook:

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"alert_type": "test", "message": "Something happened"}'
```

## Health

```bash
curl http://localhost:8000/health
```

## Configuration

Set in `.env`:

- `CENTRALMIND_COMMAND`
- `LLM_MODEL` + API key
- `OUTPUT_WEBHOOK_URL` (optional)
- `SLACK_WEBHOOK_URL` (optional)

Logging always happens. External delivery only if URLs are configured.

## Architecture

Webhook → Build context → LLM with stable tools (`search`, `execute`, `post_notification`) → Dynamic mapping to central-mind tools → Log + optional external post
