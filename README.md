# CentralMind Gateway

Minimal, generic webhook event processor using your **central-mind** MCP server.

## Philosophy

- Webhook-only
- Fully generic
- Dynamic tool discovery
- Extremely small (3 core files)
- Logging is the default output behavior

## Project Structure

```
centralmind-gateway/
├── config.py
├── main.py
├── mcp_client.py
├── README.md
├── pyproject.toml
├── Dockerfile
└── docker-compose.yml
```

## Quick Start

```bash
git clone https://github.com/zemerick1/centralmind-gateway.git
cd centralmind-gateway

# Create environment
uv venv
source .venv/bin/activate

# Install dependencies (no need to install the package itself)
uv pip install -r pyproject.toml --extra dev   # or just the main deps

# Or simply:
uv pip install fastapi uvicorn pydantic-settings httpx litellm mcp
```

### Run the gateway

**Recommended way (no installation needed):**

```bash
uv run uvicorn main:app --reload
```

Or:

```bash
python -m uvicorn main:app --reload
```

## Test

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"alert_type": "test", "message": "Test event"}'
```

Check the logs — the LLM output will be printed.

## Health Check

```bash
curl http://localhost:8000/health
```

## Configuration

Create a `.env` file:

```env
CENTRALMIND_COMMAND=python -m centralmind

LLM_MODEL=xai/grok-3-latest
XAI_API_KEY=your_key_here

# Optional
OUTPUT_WEBHOOK_URL=...
SLACK_WEBHOOK_URL=...
```

## Notes

- You do **not** need to run `pip install -e .`. This project is intentionally structured as a small application, not a distributable package.
- Logging is the default. External webhooks/Slack are optional.
