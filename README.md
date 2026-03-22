# mcpgate quickstart

Get the mcpgate AI Gateway running in minutes.

## What is mcpgate?

A single MCP endpoint that connects any AI to your company tools — with policy hooks that control what the AI can do, and enrichment hooks that make it do it right.

## Prerequisites

- Docker + Docker Compose
- Registry access (provided during onboarding)
- At least one service to connect (e.g. Google Workspace, Slack, Jira)

## Setup

```bash
# 1. Clone this repo
git clone git@gitlab.com:mcpgate/quickstart.git
cd quickstart

# 2. Authenticate with the container registry
docker login registry.gitlab.com
# Use the credentials provided during onboarding

# 3. Create your environment config
cp .env.example .env
# Edit .env — see comments in the file for what each variable does

# 4. Start
docker compose up -d

# 5. Verify
curl http://localhost:3001/health
# Should return {"status": "ok"}
```

## Connect your AI

### Claude — Company-wide (recommended)

Configure once for your entire organization at [**claude.ai/admin-settings/connectors**](https://claude.ai/admin-settings/connectors). Every team member gets the gateway automatically in every Claude session — no individual setup needed.

```
Name: mcpgate
URL:  https://your-gateway-url/mcp
```

### Claude Code — Individual

For per-user setup, add to your Claude Code MCP config:

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

Add mcpgate as an App in ChatGPT. Available in every conversation with read/write separation and user consent per action.

## Architecture

```
┌──────────────┐     ┌───────────────────┐     ┌──────────────┐
│  Claude /    │     │                   │     │  Slack       │
│  ChatGPT /  │────▶│    mcpgate        │────▶│  Jira        │
│  Any MCP    │     │                   │     │  GitLab      │
│  Agent      │◀────│  pre_hooks  ──▶   │◀────│  Google      │
│             │     │  post_hooks ──▶   │     │  Notion      │
└──────────────┘     └───────────────────┘     │  Figma       │
                                               │  ...         │
                                               └──────────────┘
```

Every request flows through the hook pipeline:

1. AI sends a tool call (e.g. `jira_write_actions` → `create_issue`)
2. **Pre-hooks** run: validate, block, transform, enrich
3. Action executes against the service API
4. **Post-hooks** run: cap responses, add hints, notify

## Services

Enable a service by providing its credentials in `.env`. Only services with valid credentials activate. The gateway auto-detects what's configured.

| Service | What the AI can do |
|---------|-------------------|
| **Google Workspace** | Gmail, Calendar, Drive, Docs, Sheets, Slides (~90 actions) |
| **Slack** | Search messages, read channels, post messages |
| **Jira** | Create/update issues, transitions, worklogs, comments |
| **GitLab** | Issues, merge requests, pipelines, deployments, CI/CD |
| **Notion** | Pages, databases, blocks, comments |
| **Figma** | Files, components, comments, dev resources |
| **Grafana** | Dashboards, logs, metrics |
| **Amplitude** | Charts, active users, real-time analytics |
| **Metabase** | BI dashboards, SQL queries, schema exploration |
| **Sentry** | Error tracking, issue queries |
| **Home Assistant** | Office sensors, heating control |
| **Joan** | Desk & meeting room booking |

## Hooks

Hooks are configured in `config/tool_hooks.yaml`. The quickstart includes a production-ready set of hooks covering:

**Policy hooks** (pre):
- Destructive action confirmation for Google, Notion, Slack
- API endpoint guards for Notion, Metabase
- Jira transition prerequisite checks

**Enrichment hooks** (pre):
- Markdown → Jira ADF auto-conversion
- GitLab/Slack text normalization (fixes AI client formatting issues)
- Auto-link Jira tickets in GitLab merge requests
- Jira issue description templates

**Post-processing hooks**:
- Cross-service automation with scheduling (e.g. desk booking → schedule office preheating via Home Assistant)
- Response size capping (Metabase, Notion)
- Auth error normalization
- Missing Jira ticket reminders on MRs
- Jira transition prerequisite hints

To add your own hook, add an entry to `config/tool_hooks.yaml` and restart:

```bash
docker compose restart ai-gateway
```

## Customization

### Branding

Set these in `.env` to white-label the dashboard:

```
BRAND_NAME=YourCompany AI
BRAND_FAVICON_URL=https://yourcompany.com/favicon.ico
```

### Error reporting

When enabled, the gateway automatically reports errors back to mcpgate. We fix them and ship an updated image — you just pull.

```
MCPGATE_ISSUE_TOKEN=<provided during onboarding>
```

## Updates

```bash
docker compose pull
docker compose up -d
```

The gateway image is updated regularly. Pull to get the latest features and fixes.

## Support

Contact hello@mcpgate.de
