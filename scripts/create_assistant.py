#!/usr/bin/env python3
"""Create or update the Vapi assistant + booking tool. Prints VAPI_ASSISTANT_ID for .env."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config
from src.vapi_client import VapiClient, build_assistant_payload


def main() -> None:
    if not config.VAPI_API_KEY:
        print("Error: VAPI_API_KEY not set in .env")
        sys.exit(1)
    if not config.WEBHOOK_BASE_URL:
        print("Error: WEBHOOK_BASE_URL not set — Vapi needs your public webhook URL")
        sys.exit(1)

    assistant_id = sys.argv[1] if len(sys.argv) > 1 else config.VAPI_ASSISTANT_ID
    client = VapiClient()

    print("Creating book_appointment tool…")
    tool_id = client.ensure_booking_tool()
    print(f"Tool ID: {tool_id}")

    payload = build_assistant_payload(tool_ids=[tool_id])

    if assistant_id:
        result = client.update_assistant(assistant_id, payload)
        print(f"Updated assistant: {result.get('id', assistant_id)}")
    else:
        result = client.create_assistant(payload)
        new_id = result.get("id")
        print(f"Created assistant: {new_id}")
        print(f"\nAdd to .env:\nVAPI_ASSISTANT_ID={new_id}")


if __name__ == "__main__":
    main()
