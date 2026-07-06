#!/usr/bin/env python3
"""Import Twilio number into Vapi. Reads .env or CLI args."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
load_dotenv(ENV_PATH)

sys.path.insert(0, str(ROOT))
from src import config  # noqa: E402
from src.vapi_client import VapiClient, build_assistant_payload  # noqa: E402


def save_env(updates: dict[str, str]) -> None:
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    out: list[str] = []
    seen = set()
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


def import_twilio_number(
    *,
    number: str,
    account_sid: str,
    auth_token: str,
    assistant_id: str,
    name: str = "Lindsey Warm Caller",
) -> dict:
    headers = {
        "Authorization": f"Bearer {config.VAPI_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "provider": "twilio",
        "number": number,
        "twilioAccountSid": account_sid,
        "twilioAuthToken": auth_token,
        "assistantId": assistant_id,
        "name": name,
    }
    r = requests.post(f"{config.VAPI_BASE_URL}/phone-number", headers=headers, json=body, timeout=60)
    if r.ok:
        return r.json()
    r2 = requests.post(
        f"{config.VAPI_BASE_URL}/phone-number/import/twilio",
        headers=headers,
        json={
            "twilioPhoneNumber": number,
            "twilioAccountSid": account_sid,
            "twilioAuthToken": auth_token,
            "assistantId": assistant_id,
            "name": name,
        },
        timeout=60,
    )
    if r2.ok:
        return r2.json()
    raise RuntimeError(f"Import failed:\n  {r.status_code}: {r.text[:300]}\n  {r2.status_code}: {r2.text[:300]}")


def list_twilio_numbers(account_sid: str, auth_token: str) -> list[str]:
    r = requests.get(
        f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/IncomingPhoneNumbers.json",
        auth=(account_sid, auth_token),
        timeout=30,
    )
    r.raise_for_status()
    return [n["phone_number"] for n in r.json().get("incoming_phone_numbers", [])]


def main() -> int:
    account_sid = sys.argv[1] if len(sys.argv) > 1 else os.getenv("TWILIO_ACCOUNT_SID", "")
    auth_token = sys.argv[2] if len(sys.argv) > 2 else os.getenv("TWILIO_AUTH_TOKEN", "")
    number = sys.argv[3] if len(sys.argv) > 3 else os.getenv("TWILIO_PHONE_NUMBER", "")

    if not account_sid or not auth_token:
        print("Usage: python scripts/connect_twilio.py [ACsid] [auth_token] [+1number]")
        print("Or set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER in .env")
        print("Get creds: console.twilio.com → Account → API keys & tokens")
        return 1

    if not number:
        nums = list_twilio_numbers(account_sid, auth_token)
        if not nums:
            print("No Twilio numbers found. Buy one at console.twilio.com → Phone Numbers → Buy")
            return 1
        if len(nums) == 1:
            number = nums[0]
            print(f"Auto-selected: {number}")
        else:
            print("Multiple numbers — pass one explicitly:")
            for n in nums:
                print(f"  {n}")
            return 1

    if not number.startswith("+"):
        number = f"+1{number}"

    if not config.VAPI_API_KEY or not config.VAPI_ASSISTANT_ID:
        print("Error: VAPI_API_KEY and VAPI_ASSISTANT_ID required in .env")
        return 1

    print(f"Importing {number} into Vapi…")
    result = import_twilio_number(
        number=number,
        account_sid=account_sid,
        auth_token=auth_token,
        assistant_id=config.VAPI_ASSISTANT_ID,
    )
    phone_id = result.get("id", "")
    print(f"Imported: {result.get('number', number)}")
    print(f"VAPI_PHONE_NUMBER_ID={phone_id}")

    if phone_id:
        save_env({
            "VAPI_PHONE_NUMBER_ID": phone_id,
            "TWILIO_ACCOUNT_SID": account_sid,
            "TWILIO_PHONE_NUMBER": number,
        })
        print(f"Updated {ENV_PATH}")

    print("Done — Twilio numbers have no Vapi daily outbound cap.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
