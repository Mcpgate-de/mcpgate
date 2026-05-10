# Security Policy

## Reporting a Vulnerability

If you discover a security issue in mcpgate, please report it privately. Do **not** open a public issue.

**Preferred channels:**

- **Email:** [hello@mcpgate.de](mailto:hello@mcpgate.de)
- **In-app:** Send a security report directly via your mcpgate instance — feedback routes through the mcpgate-backend feedback relay (anonymized, no PII stored).

We aim to acknowledge reports within 2 business days and to provide a remediation plan within 10 business days for confirmed vulnerabilities.

## Supported Versions

mcpgate is rolling-release. Only the latest published image on Docker Hub (`mcpgate/mcpgate:latest`) and tagged releases on the GitLab source repository are supported. Older self-hosted instances should upgrade before reporting issues.

## Scope

In scope:

- The self-hosting distribution in this repository (`docker-compose.yaml`, configuration templates, hooks).
- The mcpgate gateway image (`mcpgate/mcpgate`).
- The mcpgate-backend feedback relay.

Out of scope:

- Vulnerabilities in upstream services (Jira, Notion, GitLab, etc.) accessed *through* mcpgate — please report those to the respective vendor.
- Issues that require physical access to the host running mcpgate or local credentials of the operator.

## Public Disclosure

We follow coordinated disclosure. After a fix has shipped and been verified, we publish details in the release notes and CHANGELOG.
