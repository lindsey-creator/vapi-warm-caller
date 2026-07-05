#!/usr/bin/env bash
# Local dev: webhook server + ngrok hint
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true

echo "Starting webhook server on :8080"
echo "In another terminal: ngrok http 8080"
echo "Then set WEBHOOK_BASE_URL in .env to the ngrok HTTPS URL"
echo ""
exec python -m flask --app src.webhook_server run --host 0.0.0.0 --port 8080
