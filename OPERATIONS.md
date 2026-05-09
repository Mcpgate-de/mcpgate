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
  "version": "2.0.75",
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

Edit config files on the volume mount, then reload without restart:

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
- `config/service_extensions/*.yaml` — YAML action definitions
- `config/tool_hooks.yaml` — pre/post hook pipeline
- `config/access_control.yaml` — domains, guests, roles
- API versions, project workflows, unsupported services

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
| Config files | Volume mount (`./config/`) | Yes |
| Imported extensions | Volume (`EXTENSIONS_DATA_DIR`) | Yes (if configured) |
| Prometheus metrics | In-memory | No (reset on restart) |
| Logs | stdout | Depends on Docker log driver |

### Backup

What to back up:
1. `.env` — your credentials
2. `config/` — access control, hooks, extensions
3. Redis data (if you need session continuity)

```bash
# Backup config
tar czf config-backup-$(date +%Y%m%d).tar.gz config/ .env

# Backup Redis
docker compose exec redis redis-cli BGSAVE
docker cp $(docker compose ps -q redis):/data/dump.rdb ./redis-backup.rdb
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
- `CORS_ALLOWED_ORIGINS environment variable is required` — set in `.env`
- `Invalid encryption key` — generate with: `python3 -c "import base64,os; print(base64.b64encode(os.urandom(32)).decode())"`
- Redis connection failed — check `REDIS_URL` and that Redis container is running

### Service shows "Not Connected"

1. Check if credentials are set in `.env`
2. Go to `/connections` and click "Connect"
3. Complete the OAuth flow in the popup

### Config changes not applied

```bash
curl -X POST http://localhost:8642/admin/reload
```

If still not working, check file permissions on the volume mount.
