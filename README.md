# CentralMind Gateway

Minimal, generic webhook event processor powered by your **central-mind** MCP server.

## Philosophy

- Webhook-only
- Fully generic core
- Dynamic MCP tool discovery
- Extremely small codebase
- Logging is the default output

## Project Structure

```text
centralmind-gateway/
├── config.py
├── main.py
├── mcp_client.py
├── pyproject.toml
├── README.md
├── Dockerfile
└── docker-compose.yml
```

## Quick Start (uv recommended)

```bash
git clone https://github.com/zemerick1/centralmind-gateway.git
cd centralmind-gateway

# Create virtual environment and install dependencies
uv sync

# Run the gateway
uv run uvicorn main:app --reload
```

### Alternative (without uv sync)

```bash
uv venv
source .venv/bin/activate
uv pip install -r pyproject.toml
uv run uvicorn main:app --reload
```

## Test It

Send a sample webhook:

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "alert_type": "ap_down",
    "ap_name": "AP-01",
    "site": "HQ",
    "message": "Access Point is down"
  }'
```

The LLM output will be logged to the console by default.

## Health Check

```bash
curl http://localhost:8000/health
```

## Configuration

Create a `.env` file in the root:

```env
CENTRALMIND_COMMAND=python -m centralmind

LLM_MODEL=xai/grok-3-latest
XAI_API_KEY=sk-...

# Optional external outputs
OUTPUT_WEBHOOK_URL=https://...
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

## Running with Docker

```bash
docker compose up --build
```

## Notes

- This is an **application**, not a library. Do not use `pip install -e .`.
- Use `uv sync` + `uv run` for the best experience.
- The gateway discovers available MCP tools (`search_*`, `execute_*`) dynamically at startup.
