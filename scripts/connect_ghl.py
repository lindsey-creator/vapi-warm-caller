#!/usr/bin/env python3
"""Connect Lindsey sub-account: find location, test API, update .env."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"


def load_env() -> dict[str, str]:
    data: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip()
    return data


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


def find_lindsey_location(token: str) -> tuple[str, str] | None:
    headers = {
        "Authorization": f"Bearer {token}",
        "Version": "2021-07-28",
        "Accept": "application/json",
    }
    r = requests.get(
        "https://services.leadconnectorhq.com/locations/search",
        headers=headers,
        params={"limit": 50},
        timeout=30,
    )
    if not r.ok:
        print(f"locations/search failed ({r.status_code}): {r.text[:300]}")
        return None
    locations = r.json().get("locations", [])
    for loc in locations:
        name = (loc.get("name") or loc.get("business", {}).get("name") or "").lower()
        if "lindsey" in name:
            return loc["id"], loc.get("name") or name
    if len(locations) == 1:
        loc = locations[0]
        return loc["id"], loc.get("name", "unknown")
    print("Available sub-accounts:")
    for loc in locations:
        print(f"  {loc['id']} | {loc.get('name')}")
    return None


def test_contacts(token: str, location_id: str) -> bool:
    headers = {
        "Authorization": f"Bearer {token}",
        "Version": "2021-07-28",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    r = requests.post(
        "https://services.leadconnectorhq.com/contacts/search",
        headers=headers,
        json={"locationId": location_id, "page": 1, "pageLimit": 1, "filters": []},
        timeout=30,
    )
    if r.ok:
        print("Contacts API: OK")
        return True
    print(f"Contacts API failed ({r.status_code}): {r.text[:300]}")
    print("→ Create Private Integration INSIDE the Lindsey sub-account (not Agency).")
    return False


def main() -> int:
    token = sys.argv[1] if len(sys.argv) > 1 else load_env().get("GHL_API_TOKEN", "")
    location_id = sys.argv[2] if len(sys.argv) > 2 else load_env().get("GHL_LOCATION_ID", "")
    if not token or not token.startswith("pit-"):
        print("Usage: python scripts/connect_ghl.py pit-your-token [location_id]")
        return 1

    if not location_id:
        found = find_lindsey_location(token)
        if found:
            location_id, name = found
            print(f"Found: {name} ({location_id})")
        else:
            print("Sub-account token — need Location ID from your GHL URL:")
            print("  https://app.gohighlevel.com/v2/location/XXXXXXXXXX/...")
            print("Usage: python scripts/connect_ghl.py pit-token LOCATION_ID")
            return 1

    if not test_contacts(token, location_id):
        return 1

    save_env({"GHL_API_TOKEN": token, "GHL_LOCATION_ID": location_id})
    print(f"Updated {ENV_PATH}")
    print("GHL connected. Next: set up Vapi keys in .env")
    return 0


if __name__ == "__main__":
    sys.exit(main())
