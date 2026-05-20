# CentralMind Gateway - Project Status Update

## Overview
CentralMind Gateway is an LLM-powered event gateway designed to integrate with Aruba Central. It receives webhooks and on-demand queries, processes them using a separate CentralMind MCP server (from `zemerick1/central-mind`) and an LLM (e.g., Grok, Gemini, OpenAI), and outputs the results to notification channels like Teams and Slack.

## Features Implemented vs. Roadmap
- **Webhook Receiver:** Implemented. There are endpoints for generic webhooks (`/webhook`) and Aruba-specific webhooks (`/webhook/aruba`).
- **On-Demand Endpoint:** Implemented (`/query`).
- **MCP Integration:** Implemented. `app/tools/aruba.py` handles communication with the external CentralMind MCP server via stdio.
- **Agent Loop / Multi-LLM Support:** Implemented. Uses LiteLLM in `app/agent.py` to route requests to the specified model with tool-calling capabilities.
- **Output Destinations:** Slack and basic generic webhooks are implemented (`app/tools/output.py`).
- **Config-driven Flows:** *Partially Implemented / Missing Feature.* The README mentions defining behavior via YAML files in the `flows/` directory (e.g., `flows/ap_down.yaml`). The file exists, but there is currently no code in the application that reads, parses, or uses these YAML definitions. The `ap_down` logic is currently hardcoded in `main.py` (`/webhook/aruba`).
- **Missing Roadmap Items:**
  - More output channels (Email via SMTP/SendGrid, Discord, PagerDuty).
  - Rich Adaptive Cards for Teams + Slack Block Kit.
  - Persistent conversation memory per site/device.
  - Web UI for testing queries and viewing logs.
  - Support for multiple CentralMind instances (multi-cluster).
  - Prometheus metrics + OpenTelemetry tracing.

## Status Check & Dependencies
- **Compilation/Run Status:** The FastAPI app runs successfully (`uv run uvicorn app.main:app`). Note that during application startup, it attempts to connect to the MCP server. If `central-mind` is not installed or running, it gracefully fails to connect but continues running the other endpoints.
- **Dependencies (MCP Server):** The project relies on the CentralMind MCP server from the repository `zemerick1/central-mind`. Full end-to-end functionality requires this separate project to be set up and accessible via the command specified in the `.env` file (default: `python -m centralmind`).
- **Packaging Bug Fixed:** The original `pyproject.toml` used `hatchling` as the build backend, but it didn't configure `tool.hatch.build.targets.wheel` or the packages directory correctly for the `app` module. This caused `uv pip install -e .` to fail with a "ValueError: Unable to determine which files to ship inside the wheel". This has been fixed in `pyproject.toml`.
- **Testing:** Pytest and `pytest-asyncio` are configured in `pyproject.toml`, but there are currently **0 tests** implemented in the codebase.

## Recommendations
1. **Implement Flow Parsing:** Add functionality to load and parse the YAML files in the `flows/` directory so that users can define custom workflows without modifying the code, as promised in the README.
2. **Add Tests:** Start adding unit tests, especially for the agent loop and webhook endpoints.
