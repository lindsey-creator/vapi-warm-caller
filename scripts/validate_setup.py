#!/usr/bin/env python3
"""Validate .env and external service connectivity before going live."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config

REQUIRED = [
    ("GHL_API_TOKEN", config.GHL_API_TOKEN),
    ("GHL_LOCATION_ID", config.GHL_LOCATION_ID),
    ("VAPI_API_KEY", config.VAPI_API_KEY),
    ("VAPI_PHONE_NUMBER_ID", config.VAPI_PHONE_NUMBER_ID),
    ("VAPI_ASSISTANT_ID", config.VAPI_ASSISTANT_ID),
    ("WEBHOOK_BASE_URL", config.WEBHOOK_BASE_URL),
    ("GCAL_CALENDAR_ID", config.GCAL_CALENDAR_ID),
]

OPTIONAL = [
    ("GHL_NURTURE_WORKFLOW_ID", config.GHL_NURTURE_WORKFLOW_ID),
    ("SUMMARY_EMAIL_TO", config.SUMMARY_EMAIL_TO),
]


def main() -> int:
    missing = [name for name, val in REQUIRED if not val]
    if missing:
        print("Missing required .env values:")
        for name in missing:
            print(f"  - {name}")
        print("\nCopy .env.example → .env and fill in credentials.")
        return 1

    if config.WEBHOOK_BASE_URL.startswith("http://"):
        print("WARNING: WEBHOOK_BASE_URL should be HTTPS for Vapi production use.")

    print("Required config: OK")
    for name, val in OPTIONAL:
        status = "set" if val else "not set (optional)"
        print(f"  {name}: {status}")

    # Live checks (best effort)
    try:
        from src.ghl_client import GHLClient

        ghl = GHLClient()
        sample = ghl.search_contacts_by_tag("form-fill", limit=1)
        print(f"GHL API: OK (search returned {len(sample)} contact(s) for form-fill)")
    except Exception as exc:
        print(f"GHL API: FAILED — {exc}")
        return 1

    try:
        from src.vapi_client import VapiClient

        vapi = VapiClient()
        if config.VAPI_ASSISTANT_ID:
            vapi._request("GET", f"/assistant/{config.VAPI_ASSISTANT_ID}")
            print("Vapi API: OK (assistant reachable)")
    except Exception as exc:
        print(f"Vapi API: FAILED — {exc}")
        return 1

    try:
        from pathlib import Path

        cred_path = Path(config.GCAL_CREDENTIALS_PATH)
        if not cred_path.exists():
            print(f"Google Calendar: credentials file missing at {cred_path}")
            return 1
        from src.gcal_client import GCalClient

        GCalClient()
        print("Google Calendar: OK (service account loaded)")
    except Exception as exc:
        print(f"Google Calendar: FAILED — {exc}")
        return 1

    print("\nAll checks passed. Ready to run:")
    print("  gunicorn -w 2 -b 0.0.0.0:8080 src.webhook_server:app")
    print("  python -m src.orchestrator --once")
    return 0


if __name__ == "__main__":
    sys.exit(main())
