# Facebook Ad Funnel Setup — GoHighLevel (Lindsey Sub-Account)

Complete setup guide for routing Facebook ad leads into the **vapi-warm-caller** warm follow-up system.

**Sub-account:** Lindsey (location ID in `.env` as `GHL_LOCATION_ID`)  
**Business:** Conrad Mortgage — Northeast Ohio  
**Related docs:** [GHL-WORKFLOW.md](./GHL-WORKFLOW.md), [README.md](../README.md)

---

## What the AI caller expects

The orchestrator polls GHL every 5 minutes (`POLL_INTERVAL_SECONDS=300`, default) for contacts with trigger tags. For Facebook form ads, the primary trigger is **`form-fill`**.

| Category | Tag | When applied |
|----------|-----|--------------|
| **Primary trigger** | `form-fill` | Any opt-in form submission (consent record) |
| Other triggers | `hot-lead`, `email-engaged-3plus`, `quiz-start`, `quiz-complete`, `webinar-attended` | Other funnels / workflows |
| **Exclusion** (never dialed) | `call-booked`, `email-replied`, `contacted`, `dnc`, `do-not-call` | Booked, replied, already contacted, opted out |
| **Post-call outcomes** | `call-booked`, `not-ready-nurture`, `call-no-answer`, `call-voicemail`, `call-wrong-number`, `needs-human-followup`, `dnc` | Applied automatically after AI calls |

**Required contact fields for dialing:** first name, **phone** (E.164 preferred), email (optional but useful for briefs).

**Compliance gate (at dial time, fails closed):**
- Must have a consent tag (`form-fill` counts)
- No exclusion tag
- No GHL DND flag on calls
- Phone number present
- Lead-local calling hours 9 AM–8 PM
- Max 3 attempts, 24h apart

---

## What was automated via API (already done)

Using the Private Integration token in `.env`, the following was verified/created programmatically:

| Resource | API support | Status |
|----------|-------------|--------|
| **Tags** | `GET/POST /locations/{locationId}/tags` | ✅ All required tags exist (including pre-existing `form-fill`) |
| **Contacts, notes, tags on contact** | Used by `ghl_client.py` at runtime | ✅ Supported |
| **Add contact to workflow** | `POST /contacts/{id}/workflow/{workflowId}` | ✅ Supported (needs workflow ID in `.env`) |
| **List workflows** | `GET /workflows/?locationId=...` | ✅ Read-only |
| **List forms / funnels** | `GET /forms/`, `GET /funnels/funnel/list` | ✅ Read-only |
| **Create workflows** | — | ❌ Not available (404) |
| **Create funnels / pages** | — | ❌ Read-only API |
| **Create forms** | — | ❌ Requires `forms.write` scope (401 with current token) |

**Re-run tag setup anytime:**

```bash
python scripts/setup_ghl_tags.py
```

**Current Lindsey sub-account inventory (as of setup):**
- Tags: `form-fill`, `hot-lead`, plus all exclusion/outcome tags above
- Funnels: template funnels present (`Affiliate Marketing Agency`, `Affiliate Marketing Agency Offer`)
- Form: `Marketing Form - Claim Offer`
- Workflows: 6 draft nurture sequences (from template import)

**No MCP server** (ClickUp, browser, etc.) provides direct GHL dashboard access — GHL setup is API + manual UI.

---

## Manual setup — Facebook ad funnel (≈30–45 min)

### Step 1: Create the funnel

1. In Lindsey sub-account → **Sites → Funnels → + New Funnel**
2. Name: **`Facebook — Mortgage Opt-In`**
3. Structure (2 steps minimum):

```
┌─────────────────────┐     submit      ┌─────────────────────┐
│  Opt-In Page        │ ──────────────► │  Thank You Page     │
│  (Facebook ad dest) │                 │  (confirmation)     │
└─────────────────────┘                 └─────────────────────┘
```

**Opt-In page content (suggested):**
- Headline: *"See what you qualify for — free, no obligation"*
- Subhead: *Conrad Mortgage helps Northeast Ohio homeowners and buyers with purchases and refinances.*
- Single CTA button: **"Get My Free Consultation"**
- Keep the page fast — one column, minimal distractions (Facebook traffic is mobile-heavy)

**Thank You page content:**
- Headline: *"You're all set!"*
- Body: *"Someone from Lindsey's team will reach out shortly. Check your phone — we may call or text from a local number."*
- Optional: embed calendar widget for self-booking (if used, also apply `call-booked` on booking to prevent duplicate AI dials)

---

### Step 2: Build the opt-in form

Inside the opt-in page, add a **Form** element (or use **Marketing → Forms** and embed).

**Required fields:**

| Field | GHL type | Required | Maps to |
|-------|----------|----------|---------|
| First Name | Text | Yes | `firstName` |
| Last Name | Text | Yes | `lastName` |
| Phone | Phone | Yes | `phone` |
| Email | Email | Yes | `email` |

**TCPA consent — required checkbox (calls):**

Add a **Checkbox** field, required, label:

> By checking this box, I consent to receive **automated and live phone calls** from Conrad Mortgage and Lindsey Conrad's team at the number I provided, including calls made using an automatic telephone dialing system or prerecorded/artificial voice, about mortgage products and services. I understand that consent is not a condition of purchase. Message and data rates may apply. I can revoke consent at any time.

> ⚠️ **Have your telecom counsel review this language** before running paid traffic. The AI caller requires call consent — email-only or SMS-only language is not sufficient for autodialed follow-up calls to wireless numbers.

**Optional SMS consent — separate checkbox (recommended):**

> By checking this box, I consent to receive **text messages** from Conrad Mortgage at the number I provided. Message frequency varies. Message and data rates may apply. Reply STOP to opt out.

Keep SMS consent separate so you can run call-only follow-up if SMS is declined.

**Form settings → On Submit:**
1. **Add tag:** `form-fill` ← critical — this is the consent record the AI caller checks
2. **Redirect:** Thank You page URL (same funnel step 2)
3. Do **not** add exclusion tags on submit

---

### Step 3: Workflow — form submit → tag + confirmation (optional)

If the form's built-in "Add tag on submit" is configured (Step 2), a separate workflow is optional. For confirmation SMS/email, create:

1. **Automation → Workflows → Create Workflow**
2. Name: **`FB Opt-In — Tag + Confirm`**
3. Trigger: **Form Submitted** → select your Facebook opt-in form
4. Actions:
   - **Add Contact Tag:** `form-fill` (redundant safety net if form already tags)
   - **Send Email** (optional): "Thanks for reaching out — Conrad Mortgage"
   - **Send SMS** (optional, only if SMS consent field = checked): short confirmation
5. **Publish** the workflow

**Do not** add `contacted` or `call-booked` on form submit — those are exclusion tags that block the AI dial.

---

### Step 4: Facebook Pixel + conversion tracking

1. **Settings → Integrations → Facebook** — connect Business Manager / Pixel
2. On the **Opt-In page**, add pixel events:
   - **PageView** on load (automatic with GHL Facebook integration)
   - **Lead** on form submit (GHL fires this when form submits if pixel is connected)
3. On the **Thank You page**, optional secondary **Lead** or custom event for deduplication
4. In Facebook Ads Manager:
   - Ad destination URL = opt-in page URL (use UTM params: `?utm_source=facebook&utm_medium=paid&utm_campaign=mortgage-optin`)
   - Conversion event = **Lead** (optimize for leads)
5. Enable **Facebook Lead Ads → GHL** sync only if using native Lead Forms; for funnel landing pages, traffic goes to your GHL URL directly

**Pixel placement notes:**
- GHL injects pixel via integration — avoid duplicating manual pixel code unless you need custom events
- Test with Facebook Pixel Helper browser extension before spending on ads
- iOS 14+ / ATT: expect under-reporting; use GHL form submissions as source of truth

---

### Step 5: Nurture workflow for "not ready" outcomes

When the AI caller marks a lead as not ready, it adds tag `not-ready-nurture` and enrolls them in `GHL_NURTURE_WORKFLOW_ID`.

1. Use or adapt draft workflow **"5. Long-Term Nurture"** (or create your own)
2. **Publish** it
3. Copy workflow ID from URL or API:

```bash
python -c "
from src.ghl_client import GHLClient
from src import config
import requests
r = requests.get(
    f'{config.GHL_BASE_URL}/workflows/',
    headers={'Authorization': f'Bearer {config.GHL_API_TOKEN}', 'Version': '2021-07-28'},
    params={'locationId': config.GHL_LOCATION_ID},
)
for w in r.json().get('workflows', []):
    if 'nurture' in w['name'].lower():
        print(w['id'], w['name'], w['status'])
"
```

4. Add to `.env`: `GHL_NURTURE_WORKFLOW_ID=<workflow-id>`

---

### Step 6: Wire exclusion tags elsewhere

Apply these automatically from other automations so the AI caller never double-dials:

| Tag | Apply when |
|-----|------------|
| `call-booked` | Calendar booking confirmed (AI or human) |
| `email-replied` | Workflow: inbound email reply detected |
| `contacted` | Human team manually contacted lead |
| `dnc` | Opt-out keyword, "remove me" on call, or manual |

The AI caller also applies `call-booked`, `dnc`, and outcome tags after calls automatically.

---

## How leads reach the AI caller (poll flow)

```
Facebook Ad → GHL Opt-In Page → Form Submit
                                      │
                                      ▼
                              Tag: form-fill
                              Contact created/updated
                                      │
                                      ▼
                    orchestrator polls GHL every 5 min
                    (TriggerMonitor in src/triggers.py)
                                      │
                                      ▼
                         Compliance gate (src/compliance.py)
                         consent ✓  exclusion ✗  phone ✓  hours ✓
                                      │
                                      ▼
                              Vapi outbound call
                                      │
                                      ▼
                         Post-call: GHL note + outcome tag
                         Booked → Google Calendar event
                         Not ready → nurture workflow
```

**Environment:** `TRIGGER_MODE=poll` (default) — no webhook needed for Facebook funnel leads.

**Test before going live:**

1. Submit the form with your own phone number
2. Confirm contact has tag `form-fill` and a valid phone in GHL
3. Run: `python -m src.orchestrator --once --dry-run` (queues without dialing)
4. Run: `python -m src.orchestrator --once` (live call to yourself)
5. Verify GHL note, outcome tag, and calendar event

---

## Facebook ad campaign checklist

- [ ] Funnel published with custom domain or GHL subdomain
- [ ] Form fields: first name, last name, phone, email
- [ ] TCPA call consent checkbox (required)
- [ ] Tag `form-fill` on submit
- [ ] Thank you page live
- [ ] Facebook pixel connected; Lead event firing
- [ ] Ad URL points to opt-in page with UTMs
- [ ] All required tags exist (`python scripts/setup_ghl_tags.py`)
- [ ] Nurture workflow published; `GHL_NURTURE_WORKFLOW_ID` in `.env`
- [ ] Orchestrator running (`python -m src.orchestrator` or Render cron)
- [ ] Self-test call completed successfully

---

## API reference (for developers)

What `ghl_client.py` uses today:

| Operation | Endpoint | Automatable |
|-----------|----------|-------------|
| Search contacts by tag | `POST /contacts/search` | Yes |
| Get/create/update contact | `GET/POST /contacts/` | Yes |
| Add tags to contact | `POST /contacts/{id}/tags` | Yes |
| Add note | `POST /contacts/{id}/notes` | Yes |
| Enroll in workflow | `POST /contacts/{id}/workflow/{id}` | Yes |
| List/create location tags | `GET/POST /locations/{id}/tags` | Yes |
| List workflows | `GET /workflows/` | Read only |
| List forms/funnels | `GET /forms/`, `GET /funnels/funnel/list` | Read only |
| Create workflows/funnels/forms | — | **Not supported** |

Scopes needed in Private Integration: contacts, tags, workflows (read + execute), locations/tags. Form and funnel **creation** remains a dashboard task.

---

## Existing template assets (optional reuse)

Your Lindsey sub-account already has template assets you can repurpose instead of building from scratch:

- **Funnel:** `Affiliate Marketing Agency Offer` — has demo/booking/thank-you steps; adapt copy for mortgage
- **Form:** `Marketing Form - Claim Offer` — add TCPA checkbox + `form-fill` tag on submit
- **Workflows:** Draft nurture sequences — publish and connect as needed

Recommended: create a **new** dedicated Facebook funnel rather than modifying the generic template, so pixel events and UTM tracking stay clean.
