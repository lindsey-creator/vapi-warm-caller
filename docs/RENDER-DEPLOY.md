# Render deploy — paste these from your local .env after connecting GitHub repo

## Required (copy from .env)

GHL_API_TOKEN=pit-...
GHL_LOCATION_ID=3nUeqiIgQEtLuQJUbWVO
VAPI_API_KEY=...
VAPI_PHONE_NUMBER_ID=...          # Twilio-imported ID after connect_twilio.py
VAPI_ASSISTANT_ID=42a271b2-a5ef-403c-b6cb-2e3c1dab8c33
VAPI_WEBHOOK_SECRET=...
WEBHOOK_BASE_URL=https://vapi-warm-caller-webhook.onrender.com
VAPI_VOICE_ID=m3Lqbe1QZb4jjrysBIMi
GHL_INBOUND_WEBHOOK_SECRET=...

## After first deploy

1. Copy the web service URL from Render dashboard
2. Set WEBHOOK_BASE_URL to that URL (no trailing slash)
3. Run locally: `python scripts/update_webhook_url.py https://YOUR-APP.onrender.com`
4. Redeploy or update WEBHOOK_BASE_URL in Render env

## Optional

GHL_NURTURE_WORKFLOW_ID=
GCAL_CALENDAR_ID=your-real@gmail.com
GCAL_CREDENTIALS_PATH=credentials/service_account.json  # upload via secret file

## Deploy steps

1. Push branch to GitHub
2. render.com → New → Blueprint → connect lindsey-creator/vapi-warm-caller
3. Paste env vars above
4. Deploy
5. Run update_webhook_url.py with Render URL
