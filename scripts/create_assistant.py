#!/usr/bin/env python3
"""Create or update outbound + inbound Vapi assistants and wire the phone number for callbacks."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config
from src.vapi_client import (
    VapiClient,
    build_assistant_payload,
    build_inbound_assistant_payload,
)

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def save_env(updates: dict[str, str]) -> None:
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in updates:
                out.append(f"{key}={updates[key]}")
                seen.add(key)
            else:
                out.append(line)
        else:
            out.append(line)
    for key, val in updates.items():
        if key not in seen:
            out.append(f"{key}={val}")
    ENV_PATH.write_text("\n".join(out) + "\n")


def _sync_assistant(
    client: VapiClient,
    *,
    assistant_id: str | None,
    payload: dict,
    label: str,
) -> str:
    if assistant_id:
        result = client.update_assistant(assistant_id, payload)
        synced_id = result.get("id", assistant_id)
        print(f"Updated {label} assistant: {synced_id}")
        return synced_id

    result = client.create_assistant(payload)
    new_id = result.get("id", "")
    print(f"Created {label} assistant: {new_id}")
    return new_id


def main() -> None:
    if not config.VAPI_API_KEY:
        print("Error: VAPI_API_KEY not set in .env")
        sys.exit(1)
    if not config.WEBHOOK_BASE_URL:
        print("Error: WEBHOOK_BASE_URL not set — Vapi needs your public webhook URL")
        sys.exit(1)

    outbound_id = sys.argv[1] if len(sys.argv) > 1 else config.VAPI_ASSISTANT_ID
    inbound_id = config.VAPI_INBOUND_ASSISTANT_ID
    client = VapiClient()

    print("Creating book_appointment tool…")
    tool_id = client.ensure_booking_tool()
    print(f"Tool ID: {tool_id}")

    outbound_payload = build_assistant_payload(tool_ids=[tool_id])
    outbound_id = _sync_assistant(
        client,
        assistant_id=outbound_id,
        payload=outbound_payload,
        label="outbound",
    )

    inbound_payload = build_inbound_assistant_payload(tool_ids=[tool_id])
    inbound_id = _sync_assistant(
        client,
        assistant_id=inbound_id,
        payload=inbound_payload,
        label="inbound",
    )

    env_updates: dict[str, str] = {}
    if outbound_id:
        env_updates["VAPI_ASSISTANT_ID"] = outbound_id
    if inbound_id:
        env_updates["VAPI_INBOUND_ASSISTANT_ID"] = inbound_id
    if env_updates:
        save_env(env_updates)

    if config.VAPI_PHONE_NUMBER_ID and inbound_id:
        client.sync_inbound_phone_number(inbound_id)
        print(f"Phone number {config.VAPI_PHONE_NUMBER_ID} → inbound assistant {inbound_id}")
    elif not config.VAPI_PHONE_NUMBER_ID:
        print("Note: VAPI_PHONE_NUMBER_ID not set — run scripts/connect_twilio.py to wire inbound calls")

    if not config.VAPI_ASSISTANT_ID and outbound_id:
        print(f"\nAdd to .env:\nVAPI_ASSISTANT_ID={outbound_id}")
    if not config.VAPI_INBOUND_ASSISTANT_ID and inbound_id:
        print(f"VAPI_INBOUND_ASSISTANT_ID={inbound_id}")


if __name__ == "__main__":
    main()
