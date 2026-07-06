#!/usr/bin/env python3
"""Set WEBHOOK_BASE_URL in .env and re-sync Vapi assistant + booking tool."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402
from src.vapi_client import (
    VapiClient,
    build_assistant_payload,
    build_inbound_assistant_payload,
)  # noqa: E402


def save_webhook_url(url: str) -> None:
    url = url.rstrip("/")
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    out: list[str] = []
    seen = False
    for line in lines:
        if line.startswith("WEBHOOK_BASE_URL="):
            out.append(f"WEBHOOK_BASE_URL={url}")
            seen = True
        else:
            out.append(line)
    if not seen:
        out.append(f"WEBHOOK_BASE_URL={url}")
    ENV_PATH.write_text("\n".join(out) + "\n")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/update_webhook_url.py https://your-app.onrender.com")
        return 1

    url = sys.argv[1].rstrip("/")
    save_webhook_url(url)

    # reload config
    import importlib
    import src.config as cfg_mod

    importlib.reload(cfg_mod)

    client = VapiClient()
    tool_id = "601159c0-9941-4ae1-b9b6-c49d50b1acb5"
    payload = build_assistant_payload(tool_ids=[tool_id])
    client.update_assistant(config.VAPI_ASSISTANT_ID, payload)
    if config.VAPI_INBOUND_ASSISTANT_ID:
        inbound_payload = build_inbound_assistant_payload(tool_ids=[tool_id])
        client.update_assistant(config.VAPI_INBOUND_ASSISTANT_ID, inbound_payload)
        client.sync_inbound_phone_number(config.VAPI_INBOUND_ASSISTANT_ID)
    print(f"WEBHOOK_BASE_URL={url}")
    print(f"Assistant webhook: {url}/vapi/webhook")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
