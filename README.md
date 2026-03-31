# mcpgate

Self-hosted MCP gateway — connect any AI to your company tools with policy hooks.

## Quick Start

```bash
# 1. Clone and start
git clone https://gitlab.com/mcpgate/mcpgate.git
cd mcpgate
docker compose up -d

# 2. Open the setup wizard
open http://localhost:3001
```

That's it. No `.env` file needed. The setup wizard walks you through login, branding, team, and connecting services. Secrets are auto-generated on first start.

> **Already have an `.env`?** It still works — environment variables take priority over wizard config.

## Connect your AI

After setup, connect your AI client from the dashboard:

### Claude — Company-wide (recommended)

Configure once at [**claude.ai/admin-settings/connectors**](https://claude.ai/admin-settings/connectors):

```
Name: mcpgate
URL:  https://your-gateway-url/mcp
```

### Claude Code

```bash
claude mcp add mcpgate https://your-gateway-url/mcp -s user -t http
```

### ChatGPT

Settings → Apps → Add App → OAuth → enter your MCP URL.

### Codex / Gemini CLI

```bash
codex mcp add mcpgate --url https://your-gateway-url/mcp
gemini mcp add --transport http mcpgate https://your-gateway-url/mcp
```

## Architecture

```
+------------+      +------------------+      +------------+
| Claude /   |      |                  |      | Slack      |
| ChatGPT /  |----->|     mcpgate      |----->| Jira       |
| Any MCP    |      |                  |      | GitLab     |
| Agent      |<-----|  pre_hooks  -->  |<-----| Google     |
|            |      |  post_hooks -->  |      | Notion     |
+------------+      +------------------+      | Figma      |
                                              | ...        |
                                              +------------+
```

Every request flows through the hook pipeline:

1. AI sends a tool call (e.g. `jira_write_actions` → `create_issue`)
2. **Pre-hooks** run: validate, block, transform, enrich
3. Action executes against the service API
4. **Post-hooks** run: cap responses, add hints, notify

## Authentication

| Method | Use case |
|--------|----------|
| **Broker login** | Google/Microsoft sign-in, zero config (default) |
| **OIDC SSO** | Your own identity provider (Google, Microsoft, Okta, Keycloak, Auth0) |
| **Magic Links** | Email-based login for external collaborators |

SSO and service credentials are configured through the setup wizard or `.env`. See `.env.example` for the full reference.

## Services

20+ integrations. Enable a service by entering credentials in the setup wizard or `.env`. Only configured services activate.

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
| **WordPress** | Posts, pages, Yoast SEO metadata (multi-instance) |
| **Home Assistant** | Office sensors, heating control |
| **Joan** | Desk & meeting room booking |

## Hooks

Policy and enrichment hooks in `config/tool_hooks.yaml`:

- **Policy**: destructive action confirmation, API endpoint guards, transition checks
- **Enrichment**: Markdown → ADF conversion, text normalization, auto-linking, templates
- **Post-processing**: response capping, cross-service automation, auth error handling

Hot-reload without restart:

```bash
curl -X POST http://localhost:3001/admin/reload
```

See [OPERATIONS.md](OPERATIONS.md) for details.

## Customization

Branding, access control, and hooks are configurable through the setup wizard or config files. White-label the dashboard with your company name, logo, and colors.

## Updates

```bash
docker compose pull
docker compose up -d
```

## Configuration Reference

For advanced configuration, create a `.env` file from the template:

```bash
cp .env.example .env
```

See `.env.example` for all available options including OIDC, service credentials, AI features, and error reporting.

## Operations

See [OPERATIONS.md](OPERATIONS.md) for health checks, metrics, hot-reload, extensions, and troubleshooting.

## Support

Contact hello@mcpgate.de

## License

Business Source License 1.1. See [LICENSE](LICENSE).

Personal and internal business use permitted, including production. Offering mcpgate as a hosted service requires a commercial license. See [COMMERCIAL.md](COMMERCIAL.md).
