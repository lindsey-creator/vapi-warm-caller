#!/usr/bin/env python3
"""Ensure all vapi-warm-caller tags exist in the Lindsey GHL sub-account."""

from __future__ import annotations

import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402
from src.loan_campaigns import all_loan_ghl_tags  # noqa: E402

# Trigger, consent, exclusion, post-call outcome, and loan campaign tags.
REQUIRED_TAGS: tuple[str, ...] = (
    # Consent / trigger tags (config.CONSENT_TAGS + TRIGGERS)
    "form-fill",
    "hot-lead",
    "email-engaged-3plus",
    "quiz-start",
    "quiz-complete",
    "webinar-attended",
    # Loan campaign tags (src.loan_campaigns)
    *all_loan_ghl_tags(),
    # Exclusion tags (config.GLOBAL_EXCLUSION_TAGS)
    "call-booked",
    "email-replied",
    "contacted",
    "dnc",
    # Outcome tags (config.OUTCOME_TAGS)
    "not-ready-nurture",
    "call-no-answer",
    "call-voicemail",
    "call-wrong-number",
    "needs-human-followup",
    # Inbound webhook marker
    "ai-caller-inbound",
)


def main() -> int:
    if not config.GHL_API_TOKEN or not config.GHL_LOCATION_ID:
        print("Set GHL_API_TOKEN and GHL_LOCATION_ID in .env first.")
        return 1

    headers = {
        "Authorization": f"Bearer {config.GHL_API_TOKEN}",
        "Version": "2021-07-28",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    loc = config.GHL_LOCATION_ID
    base = config.GHL_BASE_URL

    r = requests.get(f"{base}/locations/{loc}/tags", headers=headers, timeout=30)
    r.raise_for_status()
    existing = {t["name"].lower() for t in r.json().get("tags", [])}

    created = 0
    for tag in REQUIRED_TAGS:
        if tag.lower() in existing:
            print(f"  ok  {tag}")
            continue
        resp = requests.post(
            f"{base}/locations/{loc}/tags",
            headers=headers,
            json={"name": tag},
            timeout=30,
        )
        if resp.ok:
            print(f"  +   {tag}")
            created += 1
        else:
            print(f"  FAIL {tag}: {resp.status_code} {resp.text[:120]}")

    print(f"\nDone. Created {created} tag(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
