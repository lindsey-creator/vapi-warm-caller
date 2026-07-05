#!/usr/bin/env bash
# Bootstrap local dev — run once after cloning
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== vapi-warm-caller setup ==="

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env — fill in your API keys next."
fi

mkdir -p data credentials

echo ""
echo "Running demo loop (no API keys needed)..."
python scripts/demo_loop.py

echo ""
echo "=== Next: fill .env with these 5 essentials ==="
echo "  1. GHL_API_TOKEN + GHL_LOCATION_ID     (GoHighLevel → Private Integrations)"
echo "  2. VAPI_API_KEY + VAPI_PHONE_NUMBER_ID   (dashboard.vapi.ai)"
echo "  3. WEBHOOK_BASE_URL                      (public HTTPS — Render or ngrok)"
echo ""
echo "Then run:"
echo "  python scripts/validate_setup.py"
echo "  python scripts/create_assistant.py"
echo "  gunicorn -w 2 -b 0.0.0.0:8080 src.webhook_server:app"
echo "  python -m src.orchestrator --once --dry-run"
