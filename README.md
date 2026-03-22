# mcpgate quickstart

Get the mcpgate AI Gateway running in minutes.

## Prerequisites

- Docker + Docker Compose
- Registry access (provided during onboarding)

## Setup

```bash
# 1. Clone this repo
git clone git@gitlab.com:mcpgate/quickstart.git
cd quickstart

# 2. Authenticate with the container registry
docker login registry.gitlab.com

# 3. Create your environment config
cp .env.example .env
# Edit .env with your credentials (see comments in the file)

# 4. Start
docker compose up -d

# 5. Verify
curl http://localhost:3001/health
```

## Connect your AI

### Claude — Company-wide (recommended)

Configure once for your entire organization at **claude.ai → Admin → Integrations → MCP Servers**. Every team member gets the gateway automatically in every Claude session — no individual setup needed.

```
Name: mcpgate
URL:  https://your-gateway-url/mcp
```

### Claude Code — Individual

If you prefer per-user setup, add to your Claude Code MCP config:

```json
{
  "mcpServers": {
    "mcpgate": {
      "type": "http",
      "url": "https://your-gateway-url/mcp"
    }
  }
}
```

### ChatGPT

Configure as a Custom GPT with Actions pointing to your gateway's OpenAPI endpoint. Supports read/write separation with user consent per action.

## Configuration

### Services

Enable services by providing their credentials in `.env`. Only services with valid credentials will be available.

### Hooks

Customize `config/hooks.yaml` to add policy and enrichment hooks. See the comments in the file for examples.

### Updates

```bash
docker compose pull
docker compose up -d
```

## Support

Contact hello@mcpgate.de
