#!/bin/sh
# Container entrypoint. In order:
#   1. make the database ready (extension, app role, migrations) — idempotent
#   2. start the LiteLLM gateway on localhost:4000
#   3. run the API on $PORT, serving the web UI from "/"
set -eu

cd /app/apps/api

echo "[start] preparing database"
python /app/infra/deploy/bootstrap_db.py
python -m alembic upgrade head

# Tracing is optional: without Langfuse keys the gateway must not try to log
# to it, so the callback line is dropped from a copy of the config.
GATEWAY_CONFIG=/tmp/litellm.yaml
if [ -n "${LANGFUSE_PUBLIC_KEY:-}" ] && [ -n "${LANGFUSE_SECRET_KEY:-}" ]; then
  cp /app/infra/litellm/config.yaml "$GATEWAY_CONFIG"
  echo "[start] gateway tracing to ${LANGFUSE_HOST:-langfuse}"
else
  grep -v "success_callback" /app/infra/litellm/config.yaml > "$GATEWAY_CONFIG"
  echo "[start] gateway tracing off (no Langfuse keys)"
fi

# The gateway reads DATABASE_URL from the environment as its own database
# and refuses the API's asyncpg URL, so the API-only variables are withheld
# from it. It keeps no state of its own.
echo "[start] gateway on 127.0.0.1:4000"
env -u DATABASE_URL -u DATABASE_URL_OWNER -u APP_DB_PASSWORD   /opt/litellm/bin/litellm --config "$GATEWAY_CONFIG" --host 127.0.0.1 --port 4000 &

echo "[start] api on 0.0.0.0:${PORT:-7860}"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-7860}" --proxy-headers --forwarded-allow-ips "*"
