# CentralMind Gateway

A lightweight, LLM-powered gateway that receives infrastructure webhooks from Aruba Central, Juniper Mist, and HPE GreenLake. It uses your `centralmind` MCP server to investigate alerts in real time and produces enriched, actionable notifications with clear root cause, impact, and recommended actions.

## Why This Exists

Most infrastructure monitoring platforms generate noisy alerts that lack context. When an alert fires (e.g. "Inconsistent STP Port" or "AP Down"), operators often have to manually dig through multiple systems to understand what actually happened and why.

This gateway closes that gap. When a webhook arrives, it uses an LLM + MCP tools to:

- Investigate the current state of the affected device
- Pull relevant configuration and recent events
- Determine root cause where possible
- Produce a clear, structured notification

The goal is to turn raw alerts into **investigated, explainable events**.

## How It Works

```
Webhook → Gateway → LLM + centralmind MCP Server → Enriched Notification
```

1. A monitoring platform (Aruba Central, Mist, GreenLake) sends a webhook.
2. The gateway receives the event and passes context to an LLM.
3. The LLM uses tools exposed by your `centralmind` MCP server to search specifications and execute live API calls.
4. The LLM investigates, gathers data, and produces a structured summary.
5. The gateway delivers the final notification (logged or forwarded to another system).

The gateway itself is intentionally thin. Most of the domain intelligence lives in `centralmind`.

## Key Benefits

- Reduces alert noise by adding real investigation
- Provides consistent, structured output across different platforms
- Works with existing Aruba Central, Mist, and GreenLake webhooks
- Designed to be easy to run with Docker Compose
- Extensible through the `centralmind` MCP server

## Prerequisites

Before following the Getting Started guide, make sure you have Docker and Docker Compose installed.

### Install Docker + Docker Compose (Ubuntu / Debian)

Run these commands:

```bash
# Update package index
sudo apt update

# Install required packages
sudo apt install ca-certificates curl gnupg -y

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add the Docker repository

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine + Compose plugin
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y
```

Verify installation:

```bash
docker --version
docker compose version
```

> **Note:** If you're not on Ubuntu/Debian, see the [official Docker installation docs](https://docs.docker.com/engine/install/).

---

## Getting Started (Recommended)

### Docker Compose (Preferred for Most Users)

This is the simplest and most reliable way to run the gateway in both development and production.

1. Clone both repositories (they must be in the same parent directory):

```bash
git clone https://github.com/zemerick1/central-mind.git
git clone https://github.com/zemerick1/centralmind-gateway.git
cd centralmind-gateway
```

2. Create your environment file:

```bash
cp .env.example .env
```

Edit `.env` and configure at least your LLM provider credentials.

3. Start the services:

```bash
docker compose up -d --build
```

4. Verify the gateway is healthy:

```bash
curl http://localhost:8001/health
```

5. Configure your monitoring platform to send webhooks to:

```
http://<your-host-or-ip>:8001/webhook
```

---

## Deployment Scenarios

### Local Development

WSL is excellent for development.

```bash
cd centralmind-gateway
uv pip install -e ../central-mind
uv sync
uv run uvicorn main:app --reload --port 8001
```

> **Important:** WSL is great for development but **not recommended for production** due to networking instability and long-running process limitations.

### Production / Self-Hosting (VPS or On-Prem)

Use **Docker Compose**. It solves the dependency management issues between the gateway and `centralmind` and provides a consistent runtime environment.

See the included `docker-compose.yml` for the recommended production setup.

### Not Recommended

- Running directly on WSL in production
- Running natively with `uv run` on a server without containerization (increases operational complexity)

---

## Webhook Configuration

### Aruba Central
- [Getting Started with Webhooks](https://developer.arubanetworks.com/new-central/docs/getting-started-with-webhooks)

### Juniper Mist
- [Configure Webhooks in the Mist Portal](https://www.juniper.net/documentation/us/en/software/mist/automation-integration/topics/concept/webhooks-configure-portal.html)

### HPE GreenLake
- [Configure a Webhook Handler](https://developer.greenlake.hpe.com/docs/greenlake/services/event/public/webhooks#configure-a-webhook-handler)

---

## Configuration

Configuration is handled primarily through environment variables.

| Variable                  | Default              | Description |
|---------------------------|----------------------|-----------|
| `CENTRALMIND_COMMAND`     | `centralmind`        | Command used to start the MCP server |
| `LLM_MODEL`               | `xai/grok-4.3`       | LLM model used for investigation |
| `LOG_LEVEL`               | `INFO`               | Logging level |
| `OUTPUT_WEBHOOK_URL`      | *(empty)*            | Optional external webhook for final notifications |

When running with Docker Compose, `CENTRALMIND_COMMAND=centralmind` works automatically due to Docker service name resolution.

---

## Development

If you are modifying the gateway:

```bash
git clone https://github.com/zemerick1/central-mind.git
git clone https://github.com/zemerick1/centralmind-gateway.git
cd centralmind-gateway

uv pip install -e ../central-mind
uv sync
```

Run with hot reload:

```bash
uv run uvicorn main:app --reload --port 8001
```

---

## How Investigation Works

The gateway supports multi-turn tool calling. The LLM can:

1. Use `search_*` tools to discover relevant API endpoints
2. Use `execute_*` tools to query live data from those endpoints
3. Iterate as needed (up to a configured limit)
4. Call `post_notification` with a structured summary once it has gathered enough information

The system is designed to be persistent when investigating and to handle errors gracefully (e.g. 404s from certain endpoints).

---

## Limitations

- Currently optimized for Aruba Central, Mist, and GreenLake style alerts
- Investigation quality depends heavily on the capabilities of your `centralmind` MCP server
- The LLM may occasionally make incorrect assumptions when data is incomplete
- Requires an LLM with strong tool-calling capabilities

---

## Contributing

Contributions are welcome. Please open an issue or pull request if you have improvements to the investigation logic, output formatting, or deployment experience.

---

## License

MIT License
