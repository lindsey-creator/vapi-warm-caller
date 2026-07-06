# Warm Follow-Up AI Caller — Vapi × GHL × Google Calendar

An AI voice system that makes **warm follow-up calls** to leads who already
engaged (form fills, email opens, quiz starts, webinar views) but haven't
booked. Not cold calling — every dial passes a consent check first.

```
GHL (tags/workflows) ──> Trigger Monitor ──> Compliance Gate ──> Vapi Call
                                                                    │
        Dashboard  <── SQLite Store <── Webhook Server <────────────┘
        Daily Email                        │
                              GHL notes/tags + Google Calendar booking
```

## What each piece does

| File | Job |
|---|---|
| `src/config.py` | All settings + the 5 trigger definitions |
| `src/triggers.py` | Polls GHL, matches trigger conditions, fills the queue |
| `src/compliance.py` | Consent, DNC, 9AM–8PM lead-local hours, attempt caps. Fails closed. |
| `src/orchestrator.py` | Main loop — the thing you run continuously |
| `src/vapi_client.py` | Vapi API + the full assistant definition (voice rules live here) |
| `src/webhook_server.py` | Receives Vapi call results + live booking tool calls; serves dashboard |
| `src/gcal_client.py` | Finds a free slot, books it, attaches the pre-call brief |
| `src/postcall.py` | Transcript → GHL note, outcome → tag, not-ready → nurture workflow |
| `src/daily_summary.py` | 8 PM email: calls / booked / needs-human / cost |
| `dashboard/index.html` | Live ops dashboard (auto-refreshes every 30s) |

---

## Setup (about 45 minutes)

### 1. GHL prep (10 min)
Your GHL workflows are the qualification brain. Make sure these tags get
applied automatically:

| Tag | Applied when |
|---|---|
| `form-fill` | Any form submission (this is your consent record) |
| `email-engaged-3plus` | Workflow counts 3rd email open, no reply |
| `quiz-start` / `quiz-complete` | Quiz funnel entry / completion |
| `webinar-attended` | eWebinar attendance webhook |
| `hot-lead` | Team marks contact hot |
| `call-booked` | Appointment created (exclusion tag) |
| `email-replied`, `contacted` | Exclusion tags |

Also create a **"Not Ready — Nurture"** workflow (the email sequence sent when
a lead says they're not ready) and grab its workflow ID for `.env`.

When creating the Private Integration, **select all available scopes** (GHL
shows ~24 — check every box). The UI no longer uses the old
`contacts.readonly` / `contacts.write` names; selecting all avoids missing
permissions for contacts, notes, tags, and workflows.

### 2. Vapi prep (10 min)
1. Buy/import a phone number in the Vapi dashboard → copy its **Phone Number ID**.
2. Grab your **private API key**.
3. Don't create the assistant by hand — the script does it (step 5).

### 3. Google Calendar (10 min)
1. GCP Console → new project → enable **Google Calendar API**.
2. Create a **service account**, download the JSON key to
   `credentials/service_account.json`.
3. Open Lindsey's Google Calendar → Settings → Share with the service
   account's email → **"Make changes to events."**
4. Set `GCAL_CALENDAR_ID` to Lindsey's calendar email.

### 4. Deploy the webhook server (10 min)
It needs a **public HTTPS URL** (Vapi calls into it mid-call for booking).

```bash
git clone <this repo> && cd vapi-warm-caller
cp .env.example .env        # fill it in
pip install -r requirements.txt

# Production:
gunicorn -w 2 -b 0.0.0.0:8080 src.webhook_server:app
# Behind: Cloud Run, Railway, Render, or a $6 VPS + Caddy.
# Local testing: ngrok http 8080 → use that URL as WEBHOOK_BASE_URL
```

### 5. Create the assistant (2 min)
```bash
python scripts/create_assistant.py
# → prints VAPI_ASSISTANT_ID — add it to .env
```
Re-run with the ID as an argument any time you tweak the prompt:
`python scripts/create_assistant.py <assistant_id>`

### 6. Run the orchestrator
```bash
python -m src.orchestrator          # continuous (systemd/supervisor recommended)
python -m src.orchestrator --once   # or cron every 5 min
```

### 7. Daily summary cron
```
0 20 * * * cd /opt/vapi-warm-caller && python -m src.daily_summary
```

### systemd units (recommended)
```ini
# /etc/systemd/system/aicaller-orchestrator.service
[Unit]
Description=AI Caller Orchestrator
After=network.target
[Service]
WorkingDirectory=/opt/vapi-warm-caller
EnvironmentFile=/opt/vapi-warm-caller/.env
ExecStart=/usr/bin/python3 -m src.orchestrator
Restart=always
[Install]
WantedBy=multi-user.target
```
Duplicate for the webhook server with
`ExecStart=/usr/local/bin/gunicorn -w 2 -b 0.0.0.0:8080 src.webhook_server:app`.

---

## Testing

```bash
pytest tests/ -v        # 34 tests: compliance gate, triggers, outcomes, store, booking parser
```

**Before going live, run the full loop on yourself:**
1. Tag your own contact record `form-fill` in GHL.
2. `python -m src.orchestrator --once`
3. Take the call. Try the objections. Ask "is this AI?" Ask about rates
   (it must deflect). Book a slot.
4. Check: GHL note + tag written, calendar event with brief, dashboard updated.

## Compliance posture (read this once)
- **Consent**: only contacts carrying an opt-in tag get called. Form fill = consent.
- **DNC**: any opt-out tag or GHL DND flag blocks the dial — checked at dial
  time, not queue time, so a same-day opt-out is honored. A "take me off your
  list" during the call auto-applies the `dnc` tag.
- **Hours**: 9 AM–8 PM in the **lead's** timezone (falls back to Eastern).
- **Attempts**: max 3 per lead, minimum 24h apart.
- **Recording**: on (Ohio one-party consent). Recording URL is logged to GHL.
- The gate **fails closed** — if GHL can't be reached to verify a contact, the call doesn't happen.
- One thing code can't do for you: confirm with your telecom counsel that your
  form language supports calls (not just email/SMS), especially for any
  wireless-number TCPA exposure. Cheap conversation, expensive lawsuit.

## Cost model
~$0.09–0.13/min on Vapi (GPT-4o + ElevenLabs turbo + Deepgram). A 3-minute
qualified conversation ≈ $0.30–0.40. At 50 calls/day averaging 2 min:
**~$10–13/day**. Watch actuals on the dashboard's spend cell — it pulls
Vapi's real per-call cost, not an estimate.

## Tuning levers
- **Prompt/voice**: `SYSTEM_PROMPT` and the `voice` block in `src/vapi_client.py`, then re-run `create_assistant.py <id>`.
- **Triggers**: edit `TRIGGERS` in `src/config.py` — pure tag logic, no code changes needed elsewhere.
- **Pacing**: `MAX_CONCURRENT_CALLS` and `POLL_INTERVAL_SECONDS` in `.env`.
- **Attempt policy**: `max_attempts_per_lead` / `min_hours_between_attempts` in `src/config.py`.
