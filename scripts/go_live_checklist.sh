#!/usr/bin/env bash
# Go-live checklist for Warm Follow-Up AI Caller
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Warm Follow-Up AI Caller — Go Live Checklist ==="
echo ""

source .venv/bin/activate 2>/dev/null || true

echo "1. Config validation"
python scripts/validate_setup.py || true
echo ""

echo "2. Tests"
pytest tests/ -q --tb=no
echo ""

echo "3. Connection status"
python3 <<'PY'
from pathlib import Path
from src import config

def ok(label, cond):
    print(f"  {'OK' if cond else 'MISSING':7} {label}")

env = Path('.env').read_text() if Path('.env').exists() else ''
ok('GHL token', bool(config.GHL_API_TOKEN.startswith('pit-')))
ok('GHL location', bool(config.GHL_LOCATION_ID))
ok('Vapi API key', bool(config.VAPI_API_KEY))
ok('Vapi assistant', bool(config.VAPI_ASSISTANT_ID))
ok('Vapi phone ID', bool(config.VAPI_PHONE_NUMBER_ID))
ok('Webhook URL (not placeholder)', 'trycloudflare' not in config.WEBHOOK_BASE_URL and 'example.com' not in config.WEBHOOK_BASE_URL)
ok('ElevenLabs voice (Lindsey 2)', config.VAPI_VOICE_ID == 'm3Lqbe1QZb4jjrysBIMi')
ok('Twilio SID in .env', bool(getattr(config, 'TWILIO_ACCOUNT_SID', '') or __import__('os').getenv('TWILIO_ACCOUNT_SID')))
ok('GCal credentials', Path(config.GCAL_CREDENTIALS_PATH).exists())
ok('GCal email real', '@' in config.GCAL_CALENDAR_ID and 'example.com' not in config.GCAL_CALENDAR_ID)
PY

echo ""
echo "=== Still need you? ==="
echo "  TWILIO  → python scripts/connect_twilio.py ACxxx auth_token +1xxxxxxxxxx"
echo "  RENDER  → connect GitHub repo, paste env vars from .env, set WEBHOOK_BASE_URL to Render URL"
echo "  GCAL    → service account JSON in credentials/ + share calendar"
echo "  After Render deploy → python scripts/update_webhook_url.py https://your-app.onrender.com"
echo ""
