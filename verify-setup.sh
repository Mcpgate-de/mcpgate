#!/usr/bin/env bash

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$ROOT_DIR/.env"
ACCESS_CONTROL_FILE="$ROOT_DIR/config/access_control.yaml"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yaml"

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

pass() {
  printf '  \033[32m%s\033[0m %s\n' "PASS" "$1"
  PASS_COUNT=$((PASS_COUNT + 1))
}

warn() {
  printf '  \033[33m%s\033[0m %s\n' "WARN" "$1"
  WARN_COUNT=$((WARN_COUNT + 1))
}

fail() {
  printf '  \033[31m%s\033[0m %s\n' "FAIL" "$1"
  FAIL_COUNT=$((FAIL_COUNT + 1))
}

section() {
  printf '\n%s\n' "$1"
}

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

env_value() {
  local key="$1"
  if [[ ! -f "$ENV_FILE" ]]; then
    return 1
  fi

  local line
  line="$(grep -E "^[[:space:]]*${key}=" "$ENV_FILE" | tail -n 1 || true)"
  if [[ -z "$line" ]]; then
    return 1
  fi

  local value="${line#*=}"
  value="$(trim "$value")"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  printf '%s' "$value"
}

has_nonempty_env() {
  local key="$1"
  local value
  value="$(env_value "$key" 2>/dev/null || true)"
  [[ -n "$value" ]]
}

is_placeholder_value() {
  local value="$1"
  [[ -z "$value" ]] && return 0
  [[ "$value" == your-* ]] && return 0
  [[ "$value" == *example.com* ]] && return 0
  [[ "$value" == changeme* ]] && return 0
  [[ "$value" == "<"*">" ]] && return 0
  return 1
}

check_required_env() {
  local key="$1"
  local label="$2"
  local value
  value="$(env_value "$key" 2>/dev/null || true)"

  if [[ -z "$value" ]]; then
    fail "$label is missing ($key)"
    return
  fi

  if is_placeholder_value "$value"; then
    fail "$label still looks like a placeholder ($key=$value)"
    return
  fi

  pass "$label is set"
}

check_optional_group() {
  local label="$1"
  shift
  local missing=0
  local key

  for key in "$@"; do
    if ! has_nonempty_env "$key"; then
      missing=1
    fi
  done

  if [[ $missing -eq 0 ]]; then
    pass "$label is configured"
  else
    warn "$label is not fully configured"
  fi
}

section "mcpgate setup verification"

section "Files"

if [[ -f "$ENV_FILE" ]]; then
  pass ".env exists"
else
  fail ".env is missing. Create it from .env.example first"
fi

if [[ -f "$ACCESS_CONTROL_FILE" ]]; then
  pass "config/access_control.yaml exists"
else
  fail "config/access_control.yaml is missing"
fi

if [[ -f "$COMPOSE_FILE" ]]; then
  pass "docker-compose.yaml exists"
else
  fail "docker-compose.yaml is missing"
fi

section "Core environment"

check_required_env "BASE_URL" "BASE_URL"
check_required_env "CORS_ALLOWED_ORIGINS" "CORS_ALLOWED_ORIGINS"
check_required_env "ADMIN_USERS" "ADMIN_USERS"
check_required_env "COMPANY_DOMAINS" "COMPANY_DOMAINS"
check_required_env "JWT_SECRET" "JWT_SECRET"
check_required_env "ENCRYPTION_KEY" "ENCRYPTION_KEY"
check_required_env "REDIS_PASSWORD" "REDIS_PASSWORD"

section "Access control"

if [[ -f "$ACCESS_CONTROL_FILE" ]]; then
  if grep -q '"example.com"' "$ACCESS_CONTROL_FILE"; then
    fail "config/access_control.yaml still contains the example.com placeholder"
  else
    pass "config/access_control.yaml does not use the example.com placeholder"
  fi

  if grep -q 'admin@example.com' "$ACCESS_CONTROL_FILE"; then
    warn "config/access_control.yaml still contains admin@example.com example entries"
  else
    pass "config/access_control.yaml admin example entries are removed"
  fi
fi

section "Login configuration"

if has_nonempty_env "OIDC_ISSUER_URL" || has_nonempty_env "OIDC_CLIENT_ID" || has_nonempty_env "OIDC_CLIENT_SECRET"; then
  check_optional_group "OIDC login" "OIDC_ISSUER_URL" "OIDC_CLIENT_ID" "OIDC_CLIENT_SECRET"
else
  warn "No OIDC login configured yet"
fi

section "Service configuration"

SERVICE_COUNT=0

if has_nonempty_env "GOOGLE_CLIENT_ID" && has_nonempty_env "GOOGLE_CLIENT_SECRET"; then
  SERVICE_COUNT=$((SERVICE_COUNT + 1))
  pass "Google Workspace credentials are configured"
fi

if has_nonempty_env "SLACK_BOT_TOKEN"; then
  SERVICE_COUNT=$((SERVICE_COUNT + 1))
  pass "Slack credentials are configured"
fi

if has_nonempty_env "JIRA_OAUTH_CLIENT_ID" && has_nonempty_env "JIRA_OAUTH_CLIENT_SECRET" && has_nonempty_env "JIRA_BASE_URL"; then
  SERVICE_COUNT=$((SERVICE_COUNT + 1))
  pass "Jira credentials are configured"
fi

if has_nonempty_env "GITLAB_OAUTH_CLIENT_ID" && has_nonempty_env "GITLAB_OAUTH_CLIENT_SECRET" && has_nonempty_env "GITLAB_BASE_URL"; then
  SERVICE_COUNT=$((SERVICE_COUNT + 1))
  pass "GitLab credentials are configured"
fi

if has_nonempty_env "NOTION_OAUTH_CLIENT_ID" && has_nonempty_env "NOTION_OAUTH_CLIENT_SECRET"; then
  SERVICE_COUNT=$((SERVICE_COUNT + 1))
  pass "Notion credentials are configured"
fi

if has_nonempty_env "FIGMA_OAUTH_CLIENT_ID" && has_nonempty_env "FIGMA_OAUTH_CLIENT_SECRET"; then
  SERVICE_COUNT=$((SERVICE_COUNT + 1))
  pass "Figma credentials are configured"
fi

if has_nonempty_env "GRAFANA_URL" && has_nonempty_env "GRAFANA_API_KEY"; then
  SERVICE_COUNT=$((SERVICE_COUNT + 1))
  pass "Grafana credentials are configured"
fi

if has_nonempty_env "AMPLITUDE_API_KEY" && has_nonempty_env "AMPLITUDE_SECRET_KEY"; then
  SERVICE_COUNT=$((SERVICE_COUNT + 1))
  pass "Amplitude credentials are configured"
fi

if has_nonempty_env "SENTRY_AUTH_TOKEN"; then
  SERVICE_COUNT=$((SERVICE_COUNT + 1))
  pass "Sentry credentials are configured"
fi

if has_nonempty_env "METABASE_URL" && has_nonempty_env "METABASE_GOOGLE_CLIENT_ID" && has_nonempty_env "METABASE_GOOGLE_CLIENT_SECRET"; then
  SERVICE_COUNT=$((SERVICE_COUNT + 1))
  pass "Metabase credentials are configured"
fi

if [[ $SERVICE_COUNT -eq 0 ]]; then
  warn "No service credentials detected yet"
else
  pass "$SERVICE_COUNT service configuration block(s) detected"
fi

section "Docker / health"

OAUTH_PORT="$(env_value "OAUTH_PORT" 2>/dev/null || true)"
if [[ -z "$OAUTH_PORT" ]]; then
  OAUTH_PORT=3001
fi
HEALTH_URL="http://localhost:${OAUTH_PORT}/health"

if command -v docker >/dev/null 2>&1; then
  pass "docker is installed"
else
  fail "docker is not installed or not on PATH"
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  pass "docker compose is available"
else
  fail "docker compose is not available"
fi

if command -v curl >/dev/null 2>&1; then
  pass "curl is installed"
else
  fail "curl is not installed"
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  if [[ -f "$ENV_FILE" ]]; then
    if docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps --status running >/dev/null 2>&1; then
      if docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps --status running | grep -q mcpgate; then
        pass "mcpgate container is running"
      else
        warn "docker compose stack is available, but mcpgate is not running"
      fi
    else
      warn "docker compose stack is not running yet"
    fi
  else
    warn "Skipping docker compose stack check because .env does not exist yet"
  fi
fi

if command -v curl >/dev/null 2>&1; then
  health_response="$(curl -fsS "$HEALTH_URL" 2>/dev/null || true)"
  if [[ -n "$health_response" ]]; then
    pass "an HTTP health endpoint responds at $HEALTH_URL"
    if printf '%s' "$health_response" | grep -Eq '"status"[[:space:]]*:[[:space:]]*"?(ok|healthy|degraded)"?'; then
      pass "health response contains a valid status"
    else
      warn "health endpoint responded, but status field was not recognized"
    fi
  else
    warn "health endpoint did not respond at $HEALTH_URL"
  fi
fi

section "Summary"

printf '  PASS: %s\n' "$PASS_COUNT"
printf '  WARN: %s\n' "$WARN_COUNT"
printf '  FAIL: %s\n' "$FAIL_COUNT"

if [[ $FAIL_COUNT -gt 0 ]]; then
  printf '\nSetup verification failed. Fix the FAIL items first.\n'
  exit 1
fi

if [[ $WARN_COUNT -gt 0 ]]; then
  printf '\nSetup verification completed with warnings.\n'
  exit 0
fi

printf '\nSetup verification completed successfully.\n'
