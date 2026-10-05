# Operations Guide

Day-2 operations for your mcpgate deployment.

## Endpoints

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/health` | GET | None | Health check (Redis status, version) |
| `/metrics` | GET | None | Prometheus metrics |
| `/connections` | GET | Session | User dashboard (service connections) |
| `/admin/reload` | POST | Admin | Hot-reload all config files |
| `/admin/extensions` | GET | Admin | Extension management dashboard |

## Health Check

```bash
curl http://localhost:8642/health
```

```json
{
  "status": "healthy",
  "version": "<image version>",
  "components": {
    "redis": {"status": "up", "latency_ms": 1.0}
  }
}
```

- `healthy` — all components up
- `degraded` — Redis down (gateway still works but sessions are in-memory only)
- Always returns HTTP 200 (prevents unnecessary container restarts)

Use in Docker Compose healthcheck (already configured in `docker-compose.yaml`):
```yaml
healthcheck:
  test: ["CMD", "curl", "-sf", "http://localhost:3001/health"]
  interval: 10s
  timeout: 5s
  retries: 3
```

## Prometheus Metrics

```bash
curl http://localhost:8642/metrics
```

Available metrics:

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `mcpgate_http_requests_total` | Counter | method, endpoint, status_code | Total HTTP requests |
| `mcpgate_http_request_duration_seconds` | Histogram | method, endpoint | Request latency |
| `mcpgate_mcp_connections_active` | Gauge | — | Active MCP connections |
| `mcpgate_mcp_requests_total` | Counter | tool_name, status, action, client_type | MCP tool calls |
| `mcpgate_mcp_request_duration_seconds` | Histogram | tool_name | MCP tool call latency |
| `mcpgate_oauth_operations_total` | Counter | operation, service, status | OAuth operations |
| `mcpgate_service_errors_total` | Counter | service, error_type | Service API errors |

### Grafana Dashboard

Add your gateway as a Prometheus scrape target:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'mcpgate'
    static_configs:
      - targets: ['mcpgate:3001']
    metrics_path: /metrics
    scrape_interval: 15s
```

## Config Hot-Reload

The image ships its config files under `/app/config`. To customize one, mount your copy over it in `docker-compose.yaml`:

```yaml
    volumes:
      - gateway-data:/app/data
      - ./config/tool_hooks.yaml:/app/config/tool_hooks.yaml:ro
      - ./config/access_control.yaml:/app/config/access_control.yaml:ro
```

The files in this repository's `config/` directory are the same templates that the image ships. Edit your copy, then reload without restart:

```bash
# Reload ALL configs (extensions, hooks, access control, etc.)
curl -X POST http://localhost:8642/admin/reload \
  -H "Cookie: mcpgate_session=YOUR_SESSION"
```

```json
{
  "success": true,
  "message": "Config reloaded in 831ms",
  "duration_ms": 831.8,
  "reloaded": {
    "extensions": {"status": "ok", "total_actions": 556},
    "tool_hooks": {"status": "ok"},
    "access_control": {"status": "ok", "domains": 2, "guests": 13}
  }
}
```

What gets reloaded:
- `modules/builtin/<service>/actions.yaml` — YAML action definitions and their service hooks
- Imported extensions in `/app/data/extensions` (or `EXTENSIONS_DATA_DIR`)
- `config/tool_hooks.yaml` — cross-cutting pre/post hook pipeline
- `config/access_control.yaml` — domains, guests, roles
- `config/api_versions.yaml` — API versions

### CI/CD Integration

After deploying a new config via git:

```bash
curl -X POST https://your-gateway/admin/reload \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

For blue/green deployments, hit both containers:

```bash
for host in blue:3001 green:3001; do
  curl -s -X POST "http://$host/admin/reload" \
    -H "Authorization: Bearer $ADMIN_TOKEN"
done
```

## Extension Management

### Import from OpenAPI

The admin dashboard can import service definitions from any OpenAPI 3.x spec:

1. Go to `/admin/extensions`
2. Enter the OpenAPI spec URL
3. Select actions to import
4. Click "Import" — saved to disk + hot-reloaded

### Disable / Enable / Delete

```bash
# Disable an imported extension (prefix with _)
curl -X POST http://localhost:8642/admin/extensions/api/disable-file \
  -H "Cookie: mcpgate_session=YOUR_SESSION" \
  -H "Content-Type: application/json" \
  -d '{"filename": "statuspage_imported.yaml"}'

# Re-enable it
curl -X POST http://localhost:8642/admin/extensions/api/enable-file \
  -H "Content-Type: application/json" \
  -d '{"filename": "_statuspage_imported.yaml"}'

# Permanently delete (imported files only)
curl -X POST http://localhost:8642/admin/extensions/api/delete-file \
  -H "Content-Type: application/json" \
  -d '{"filename": "statuspage_imported.yaml"}'
```

## Logging

The gateway outputs structured JSON logs to stdout:

```json
{"timestamp": "2026-03-27 08:00:00", "logger": "src.mcp.tool_executor", "level": "INFO", "message": "MCP tool call: jira_write_actions.create_issue"}
```

### Log Levels

Set via `LOG_LEVEL` environment variable:

| Level | What you see |
|-------|-------------|
| `ERROR` | Only errors |
| `WARNING` | Errors + warnings (default for production) |
| `INFO` | Normal operations (recommended) |
| `DEBUG` | Everything (verbose, for troubleshooting) |

Change at runtime without restart:
```bash
# Via environment variable in docker-compose
LOG_LEVEL=DEBUG docker compose up -d
```

### Structured Fields

Every log entry contains:
- `timestamp` — ISO 8601
- `logger` — Source module
- `level` — ERROR/WARNING/INFO/DEBUG
- `message` — Human-readable description
- `taskName` — Async task context (for tracing)

## Persistence

| Data | Storage | Survives restart? |
|------|---------|------------------|
| User sessions | Redis | Yes (until TTL expires) |
| OAuth tokens | Redis (encrypted) | Yes |
| Generated secrets, wizard config | `gateway-data` volume (`/app/data/gateway.env`) | Yes |
| Audit log (90-day retention) | `gateway-data` volume (`/app/data/audit.db`, SQLite) | Yes |
| Imported extensions | `gateway-data` volume (`/app/data/extensions`, or `EXTENSIONS_DATA_DIR`) | Yes |
| Config files | Baked into the image (`/app/config`), or your own mounted copies | Yes |
| Prometheus metrics | In-memory | No (reset on restart) |
| Logs | stdout | Depends on Docker log driver |

### Backup

What to back up:
1. The `gateway-data` volume — generated secrets (including `ENCRYPTION_KEY`), wizard config, audit log, imported extensions
2. `.env` and any config files you mount — if you use them
3. Redis data — sessions and encrypted OAuth tokens

Without the `ENCRYPTION_KEY` from the `gateway-data` volume (or `.env`), the stored OAuth tokens cannot be decrypted and users must reconnect their services.

```bash
# Backup the gateway-data volume (mounted at /app/data in the mcpgate container)
docker run --rm --volumes-from "$(docker compose ps -q mcpgate)" -v "$PWD":/backup alpine \
  tar czf /backup/gateway-data-$(date +%Y%m%d).tar.gz -C /app/data .

# Backup .env and mounted config files, if you use them
tar czf config-backup-$(date +%Y%m%d).tar.gz .env config/

# Backup Redis (RDB snapshot and AOF files; Redis requires the password)
docker compose exec redis redis-cli -a "${REDIS_PASSWORD:-mcpgate-default-pw}" BGSAVE
docker run --rm --volumes-from "$(docker compose ps -q redis)" -v "$PWD":/backup alpine \
  tar czf /backup/redis-data-$(date +%Y%m%d).tar.gz -C /data .
```

## Updates

```bash
docker compose pull
docker compose up -d
```

The gateway is backwards-compatible — config files from older versions work with newer images. Check `/health` for the running version.

## Troubleshooting

### Gateway won't start

```bash
docker compose logs mcpgate | head -50
```

Common issues:
- `Invalid ENCRYPTION_KEY` — the key must be base64 of 32 bytes. Generate one with: `python3 -c "import base64,secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"`
- Redis connection failed — check `REDIS_URL` and that Redis container is running

### Service shows "Not Connected"

1. Check that the service credentials are set in the setup wizard or in `.env`
2. Go to `/connections` and click "Connect"
3. Complete the OAuth flow in the popup

### Config changes not applied

```bash
curl -X POST http://localhost:8642/admin/reload
```

If still not working, check file permissions on the volume mount.
