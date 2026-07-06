# Lindsey sub-account setup (everything in one place)

## 1. Create the Lindsey sub-account in GHL

## 2. Private Integration (inside Lindsey sub-account — not Agency)
- Settings → Integrations → Private Integrations
- Name: `AI Warm Caller`
- Select **all scopes**
- Copy the `pit-...` token into `.env`

## 3. Location ID
Paste the token here and we'll auto-detect it, or grab from the URL:
`.../location/XXXXXXXXXX/...`

## 4. Tags & workflows (all inside Lindsey sub-account)

**Facebook ad funnel:** see [GHL-FACEBOOK-FUNNEL-SETUP.md](./GHL-FACEBOOK-FUNNEL-SETUP.md) for the complete opt-in funnel, TCPA consent language, pixel setup, and poll flow.

**Tags (automated):** run `python scripts/setup_ghl_tags.py` to ensure all required tags exist.

Set up your forms, funnels, and workflows in Lindsey. Apply these tags:

| Tag | When |
|---|---|
| `form-fill` | Form submission (consent record) |
| `email-engaged-3plus` | 3rd email open, no reply |
| `quiz-start` / `quiz-complete` | Quiz funnel |
| `webinar-attended` | Webinar attendance |
| `hot-lead` | Manually marked hot |
| `call-booked` | Exclusion — already booked |

Exclusion tags: `email-replied`, `contacted`, `dnc`, `call-booked`

## 5. How the AI caller finds leads

With `TRIGGER_MODE=poll` (default), the orchestrator polls **Lindsey sub-account**
for contacts with trigger tags. No other sub-account involved.

## 6. Optional: inbound webhook

If you ever want an external system to push leads in, POST to `/ghl/trigger`.
Not needed for a standalone Lindsey setup.
