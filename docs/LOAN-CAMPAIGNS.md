# Loan campaigns (outbound)

Outbound warm calls use **one Vapi assistant** (`VAPI_ASSISTANT_ID`) with **per-call overrides** for the system prompt and opening line. Loan type comes from **GHL tags** on the contact — no separate assistants to maintain.

## How it works

1. A lead gets a **consent/trigger tag** (e.g. `form-fill`, `hot-lead`) — same as before.
2. Optionally they also get a **loan campaign tag** (e.g. `loan-purchase`).
3. `TriggerMonitor` resolves the campaign from tags and stores `campaign_id` on the queue row.
4. At dial time, `create_call()` passes `assistantOverrides`:
   - `firstMessage` — loan-specific opener
   - `model.messages` — full system prompt for that loan type
   - `variableValues.loanCampaign` — for debugging / webhooks

If no loan tag is present, the **general** warm follow-up campaign is used (same tone as the original single-prompt setup).

## GHL tags

| Tag | Campaign | Use when |
|-----|----------|----------|
| `loan-purchase` | Purchase / pre-approval | Buyer funnels, pre-approval forms |
| `loan-refi` | Refinance | Refi calculators, rate-check pages |
| `loan-dscr` | DSCR / investor rental | Investor landing pages, rental property offers |
| *(none)* | General | Any inquiry without a loan-specific tag |

**Trigger tags are unchanged** — you still need one of: `form-fill`, `hot-lead`, `email-engaged-3plus`, `quiz-start`, `quiz-complete`, `webinar-attended`.

**Priority:** If a contact has multiple loan tags, the first match in this order wins: `loan-dscr` → `loan-purchase` → `loan-refi`.

Create tags in GHL:

```bash
python scripts/setup_ghl_tags.py
```

## GHL workflows & forms

Tag leads at the moment you know their intent. Always pair **consent + loan type**:

| Funnel / form | Tags to apply |
|---------------|---------------|
| Home buyer opt-in | `form-fill`, `loan-purchase` |
| Refi rate check | `form-fill`, `loan-refi` |
| DSCR / investor page | `form-fill`, `loan-dscr` |
| Generic mortgage quiz | `quiz-complete` only (general campaign) |
| Hot lead from ads | `hot-lead`, `loan-purchase` (or matching loan tag) |

**Webhook pushes** (`/ghl/trigger`): include loan tags in the JSON `tags` array:

```json
{
  "phone": "+15551234567",
  "firstName": "Jane",
  "tags": ["form-fill", "loan-purchase"]
}
```

## What each campaign says

- **Purchase** — buying a home, pre-approval, rates depend on situation → book consult
- **Refi** — lower payment, cash out, rate improvement → book consult
- **DSCR** — investor/rental loans, property income vs personal docs → book consult
- **General** — original warm follow-up for any mortgage inquiry

Prompts live in `src/loan_campaigns.py`.

## Adding a new loan type

1. Add a `LoanCampaign` entry to `CAMPAIGNS` in `src/loan_campaigns.py`.
2. Add a `(ghl_tag, campaign_id)` pair to `LOAN_TAG_TO_CAMPAIGN` (set priority order).
3. Run `python scripts/setup_ghl_tags.py` to create the GHL tag.
4. Tag funnels/workflows in GHL with the new `loan-*` tag.
5. No Vapi assistant sync required — overrides are applied per call.

Example:

```python
# loan_campaigns.py
LOAN_TAG_TO_CAMPAIGN = (
    ("loan-heloc", "heloc"),  # add where you want in priority order
    ...
)

CAMPAIGNS["heloc"] = LoanCampaign(
    id="heloc",
    name="HELOC",
    ghl_tag="loan-heloc",
    focus_block="...",
    no_memory_fallback="...",
    first_message_template="Hey {{firstName}}, ...",
)
```

## Testing

```bash
pytest tests/test_loan_campaigns.py tests/test_triggers.py -q
```

Dry-run the orchestrator against tagged contacts:

```bash
python -m src.orchestrator --once --dry-run
```

## Architecture note

We chose **campaign config + single assistant + dynamic overrides** (not multiple Vapi assistants) because:

- The codebase already overrides `firstMessage` and `voice` per call in `create_call()`.
- Triggers and tags are already the source of truth in `config.py` / GHL.
- One assistant ID in `.env`; loan types are data, not infrastructure.
