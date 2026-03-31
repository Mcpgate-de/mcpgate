# mcpgate - Claude Setup Guide

> For Claude sessions helping a user set up mcpgate from this repository.
> This file is operational guidance for AI-guided onboarding, not general product documentation.

## Goal

Help the user get a working mcpgate instance running as quickly as possible with the least manual friction, while preserving the product principle that OAuth apps and tokens remain under the user's control.

Success means:
- `docker compose up -d` starts successfully (zero-config, no `.env` needed)
- the health check passes
- the setup wizard is completed (login, branding, team, services)
- at least one service is configured or clearly queued as the next step

Note: `.env` is optional. The gateway auto-generates secrets on first start and the
setup wizard handles all configuration. `.env` takes priority when present.

## Canonical Sources

Use these files as the source of truth during setup:

1. `config/setup_catalog.yaml`
   Provider console URLs, redirect URI templates, required env vars, and short setup steps.
2. `.env.example`
   Environment variable schema and user-facing config comments.
3. `README.md`
   High-level setup flow and MCP connection instructions.
4. `OPERATIONS.md`
   Day-2 operations and reload/troubleshooting workflow.

If these files disagree, treat `config/setup_catalog.yaml` as canonical for setup metadata and update the others later.

## Setup Principles

- Do not ask the user to hunt for provider URLs manually if the setup catalog already has them.
- Prefer the smallest viable setup first: one login method plus one service is enough.
- Distinguish clearly between:
  - SSO login to mcpgate itself
  - OAuth/API credentials for connected services
- For OIDC SSO, endpoint URLs should not be manually configured if discovery can handle them.
- For Google Workspace, Jira, Notion, Figma, and similar services, the user still needs their own OAuth app credentials.
- Never imply that mcpgate provides a central OAuth app when the setup model is customer-owned credentials.

## Default Flow

Follow this order unless the user explicitly wants something else:

1. `docker compose up -d` (zero-config start).
2. Open `http://localhost:3001` — setup wizard starts automatically.
3. Login via broker (Google/Microsoft) or configure own OIDC.
4. Wizard: branding, team, services.
5. Connect the first service the user cares about most.
6. Verify health and detect obvious config errors.
7. Only then add more services.

For advanced users who prefer `.env`: `cp .env.example .env`, edit, then start.

## Questions Claude Should Ask Early

Ask only for information that cannot be derived locally:

- What public `BASE_URL` should mcpgate use?
- Which login provider should users use for mcpgate: Google, Microsoft, Okta, Keycloak, or something else?
- Which service should be connected first?
- Which email domains should be allowed to log in?
- Which users should be admins?

Do not ask the user for OAuth/token endpoint URLs for standard OIDC providers if discovery already covers them.

## OIDC Rules

For SSO login:

- `OIDC_ISSUER_URL` selects the provider.
- `OIDC_CLIENT_ID` and `OIDC_CLIENT_SECRET` are still required.
- Redirect URI is `{BASE_URL}/auth/callback`.
- Google and Microsoft provider examples live in `config/setup_catalog.yaml`.

Interpretation:
- Google SSO means `OIDC_ISSUER_URL=https://accounts.google.com`
- Microsoft SSO means `OIDC_ISSUER_URL=https://login.microsoftonline.com/{TENANT_ID}/v2.0`

Claude should guide the user to the provider console URL from `config/setup_catalog.yaml`, then tell them exactly which redirect URI to paste.

## Service Setup Rules

For service connections:

- Use `config/setup_catalog.yaml` to guide the user to the correct provider console.
- Always give the exact redirect URI derived from `BASE_URL`.
- Name the exact env vars that must be filled in.
- Keep SSO and service OAuth separate in the explanation.

Examples:
- Google SSO credentials are not the same thing as Google Workspace API credentials.
- GitLab SSO is different from GitLab service access.

## Editing Rules During Setup

When helping the user configure the repo:

- Create `.env` from `.env.example` if it does not exist.
- Edit only the values needed for the chosen login method and selected services.
- Avoid enabling many services speculatively.
- Keep placeholder comments in `.env.example` intact unless intentionally improving documentation.
- If setup metadata is missing, add it to `config/setup_catalog.yaml` rather than hiding it only in prose.

## Verification

Until a dedicated `verify-setup.sh` exists, use this minimum verification flow:

```bash
docker compose up -d
curl http://localhost:3001/health
```

Then check:
- container status
- health response
- obvious startup errors in logs
- whether the configured login/service vars are present

If a future `verify-setup.sh` exists, use that script as the primary verification entry point.

## What Claude Should Optimize For

- shortest path to first working result
- precise copy-paste instructions for provider consoles
- minimal configuration surface
- no unnecessary theory unless the user asks for it

## What Claude Must Avoid

- asking the user to invent provider URLs that are already known
- mixing up SSO login with service OAuth credentials
- proposing a centralized mcpgate-owned OAuth app as if that were the intended product model
- forcing all services to be configured before first startup
