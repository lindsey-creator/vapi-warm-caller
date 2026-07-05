"""Vapi API client and assistant definition."""

from __future__ import annotations

import logging
from typing import Any

import requests

from src import config
from src.persona import build_caller_prompt

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a warm follow-up caller for {business_name}, a mortgage and real estate lending \
operation in Northeast Ohio run by Lindsey Conrad.

CONTEXT: You are calling leads who ALREADY engaged — they filled out a form, opened emails, started a quiz, \
attended a webinar, or were marked hot by the team. This is NOT cold calling. They opted in.

YOUR GOAL: Have a short, natural conversation and book a consultation on Lindsey's calendar if they're interested. \
If they're not ready, respect that and offer to follow up later.

{persona_block}

HARD RULES (never break these):
1. If they ask "Are you AI?" or "Is this a robot?" — be honest: "Yeah, I'm an AI assistant calling on \
behalf of Lindsey's team. She set me up to follow up with people who reached out. Want me to have a real \
person call you back instead?"
2. NEVER quote specific rates, APRs, loan terms, or payment amounts. Say: "Rates depend on your situation — \
Lindsey's team will walk through the numbers on the call."
3. NEVER make final lending commitments or approvals.
4. If they say "take me off your list", "stop calling", or "do not call" — apologize briefly, confirm you'll \
remove them, and end the call politely. Do NOT try to overcome this objection.
5. If they ask complex legal/compliance questions, say Lindsey's team will cover that on the consultation.

BOOKING:
- When they're interested, use the book_appointment tool to find a slot and confirm it with them.
- Confirm date, time, and timezone before booking.
- After booking, recap what happens next: "You'll get a calendar invite, and Lindsey's team will prep based \
on what we talked about."

OBJECTION HANDLING:
- "Not interested" → "Totally fair. Mind if I ask what changed, or should I check back in a few months?"
- "Bad timing" → Offer to book something further out or send info via email.
- "Already working with someone" → "Nice — if anything changes, we're here. Want me to leave your info on file?"

Keep calls under 5 minutes unless they're actively booking.
""".format(business_name=config.BUSINESS_NAME, persona_block=build_caller_prompt())


def webhook_url() -> str:
    return f"{config.WEBHOOK_BASE_URL}/vapi/webhook"


def build_book_appointment_tool(server_url: str | None = None) -> dict[str, Any]:
    url = server_url or webhook_url()
    payload: dict[str, Any] = {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book a consultation on Lindsey's calendar when the lead agrees to a time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "preferred_date": {
                        "type": "string",
                        "description": "ISO date YYYY-MM-DD the lead prefers",
                    },
                    "preferred_time": {
                        "type": "string",
                        "description": "Time like '2:00 PM' in the lead's timezone",
                    },
                    "timezone": {
                        "type": "string",
                        "description": "IANA timezone, e.g. America/New_York",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Brief context from the conversation",
                    },
                },
                "required": ["preferred_date", "preferred_time"],
            },
        },
        "server": {"url": url},
    }
    if config.VAPI_WEBHOOK_SECRET:
        payload["server"]["secret"] = config.VAPI_WEBHOOK_SECRET
    return payload


def build_assistant_payload(
    server_url: str | None = None,
    tool_ids: list[str] | None = None,
) -> dict[str, Any]:
    url = server_url or webhook_url()
    model: dict[str, Any] = {
        "provider": "openai",
        "model": "gpt-4o",
        "temperature": 0.7,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
    }
    if tool_ids:
        model["toolIds"] = tool_ids
    else:
        model["tools"] = [build_book_appointment_tool(url)]

    server_block: dict[str, Any] = {"url": url}
    if config.VAPI_WEBHOOK_SECRET:
        server_block["secret"] = config.VAPI_WEBHOOK_SECRET

    return {
        "name": f"{config.BUSINESS_NAME} Warm Follow-Up",
        "firstMessage": (
            "Hey, is this {{firstName}}? "
            "This is calling from {business} — you recently checked us out online "
            "and I wanted to follow up real quick. Got a minute?"
        ).format(business=config.BUSINESS_NAME),
        "model": model,
        "voice": {
            "provider": "11labs",
            "voiceId": "21m00Tcm4TlvDq8ikWAM",
            "model": "eleven_turbo_v2_5",
        },
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "en",
        },
        "recordingEnabled": True,
        "server": server_block,
        "serverMessages": ["end-of-call-report", "tool-calls", "status-update"],
        "endCallFunctionEnabled": True,
        "maxDurationSeconds": config.VAPI_MAX_CALL_DURATION_SECONDS,
        "analysisPlan": {
            "summaryPlan": {"enabled": True},
            "structuredDataPlan": {
                "enabled": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "outcome": {
                            "type": "string",
                            "enum": [
                                "booked",
                                "not_ready",
                                "no_answer",
                                "voicemail",
                                "wrong_number",
                                "needs_human",
                                "dnc_requested",
                                "other",
                            ],
                        },
                        "dnc_requested": {"type": "boolean"},
                    },
                },
            },
        },
    }


class VapiClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or config.VAPI_API_KEY
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{config.VAPI_BASE_URL}{path}"
        resp = self.session.request(method, url, timeout=60, **kwargs)
        if not resp.ok:
            logger.error("Vapi %s %s failed (%s): %s", method, path, resp.status_code, resp.text[:500])
        resp.raise_for_status()
        return resp.json() if resp.text else {}

    def create_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/tool", json=payload)

    def create_assistant(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("POST", "/assistant", json=payload or build_assistant_payload())

    def update_assistant(self, assistant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", f"/assistant/{assistant_id}", json=payload)

    def ensure_booking_tool(self, server_url: str | None = None) -> str:
        """Create or return the book_appointment tool ID."""
        tool_payload = build_book_appointment_tool(server_url)
        created = self.create_tool(tool_payload)
        tool_id = created.get("id")
        if not tool_id:
            raise RuntimeError(f"Failed to create Vapi tool: {created}")
        return tool_id

    def create_call(
        self,
        *,
        phone: str,
        contact_id: str,
        first_name: str = "",
        brief: str = "",
        queue_id: int | None = None,
    ) -> dict[str, Any]:
        assistant_id = config.VAPI_ASSISTANT_ID
        if not assistant_id:
            raise ValueError("VAPI_ASSISTANT_ID not configured — run scripts/create_assistant.py first")

        payload = {
            "assistantId": assistant_id,
            "phoneNumberId": config.VAPI_PHONE_NUMBER_ID,
            "customer": {
                "number": phone,
                "name": first_name or "there",
            },
            "assistantOverrides": {
                "variableValues": {
                    "firstName": first_name or "there",
                    "contactId": contact_id,
                    "queueId": str(queue_id or ""),
                    "preCallBrief": brief,
                },
            },
            "metadata": {
                "contactId": contact_id,
                "queueId": queue_id,
            },
            "maxDurationSeconds": config.VAPI_MAX_CALL_DURATION_SECONDS,
        }
        # Primary endpoint per Vapi docs; /call/phone kept as fallback for older accounts
        try:
            return self._request("POST", "/call", json=payload)
        except requests.HTTPError:
            return self._request("POST", "/call/phone", json={**payload, "type": "outboundPhoneCall"})

    def get_call(self, call_id: str) -> dict[str, Any]:
        return self._request("GET", f"/call/{call_id}")
