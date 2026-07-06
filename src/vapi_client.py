"""Vapi API client and assistant definition."""

from __future__ import annotations

import logging
from typing import Any

import requests

from src import config
from src.loan_campaigns import (
    DEFAULT_CAMPAIGN_ID,
    build_assistant_first_message_template,
    build_outbound_first_message,
    build_outbound_system_prompt,
)
from src.persona import (
    build_inbound_identity_block,
    build_inbound_second_turn_script,
)

logger = logging.getLogger(__name__)

# Default outbound prompt (general warm follow-up). Per-loan overrides via build_outbound_system_prompt().
SYSTEM_PROMPT = build_outbound_system_prompt(DEFAULT_CAMPAIGN_ID)

def build_inbound_context() -> str:
    bot = config.VAPI_INBOUND_BOT_NAME
    return f"""
INBOUND CALLBACK: They dialed you back after your outbound reach-out. Their phone rang normally; they just picked up.

OPENING (turn 1 — already handled by firstMessage):
- You answer after a brief beat — like someone picking up the phone, not an instant recording.
- Say only a short hello ("Hey, hello?"), then stop and let them respond.

SECOND TURN (right after they say hello back):
- Respond immediately — no dead air. They just greeted you; jump in the instant they finish.
- Deliver ONE continuous response in a single breath. Do not pause between parts or split into separate turns.
- Flow: introduce yourself → thank them for calling back → mention we got their inquiry. All one natural sentence.
- Example (adapt naturally, don't read robotically): "{build_inbound_second_turn_script(bot)}"
- Executive office tone — warm, confident, conversational. Then stop and let them talk.

{build_inbound_identity_block(bot)}
"""


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


def build_voice_config() -> dict[str, Any]:
    """Voice block — ElevenLabs tuned for natural phone conversation."""
    if config.VAPI_VOICE_PROVIDER == "11labs":
        return {
            "provider": "11labs",
            "voiceId": config.VAPI_VOICE_ID,
            "model": config.VAPI_ELEVENLABS_MODEL,
            "stability": config.VAPI_ELEVENLABS_STABILITY,
            "similarityBoost": config.VAPI_ELEVENLABS_SIMILARITY,
            "style": config.VAPI_ELEVENLABS_STYLE,
            "speed": config.VAPI_ELEVENLABS_SPEED,
            "useSpeakerBoost": config.VAPI_ELEVENLABS_USE_SPEAKER_BOOST,
            "optimizeStreamingLatency": config.VAPI_ELEVENLABS_STREAMING_LATENCY,
        }

    voice: dict[str, Any] = {
        "provider": config.VAPI_VOICE_PROVIDER,
        "voiceId": config.VAPI_VOICE_ID,
    }
    if config.VAPI_VOICE_VERSION:
        voice["version"] = config.VAPI_VOICE_VERSION
    return voice


def _build_transcriber_config(*, endpointing: int) -> dict[str, Any]:
    return {
        "provider": "deepgram",
        "model": "nova-2-phonecall",
        "language": "en",
        "endpointing": endpointing,
    }


def _build_start_speaking_plan(*, wait_seconds: float, inbound: bool) -> dict[str, Any]:
    plan: dict[str, Any] = {
        "waitSeconds": wait_seconds,
        "smartEndpointingPlan": {
            "provider": "livekit",
            # Aggressive curve for inbound — short "hello" back should trigger quickly (~0.2s).
            "waitFunction": "200 / (1 + exp(-10 * (x - 0.35)))",
        },
    }
    if inbound:
        plan["customEndpointingRules"] = [
            {
                "type": "customer",
                "regex": r"^(hello|hi|hey|yes|yeah|yo)[\s\.\?!,]*$",
                "timeoutSeconds": 0.12,
            },
        ]
    return plan


def _analysis_plan() -> dict[str, Any]:
    return {
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
    }


def build_outbound_cost_controls() -> dict[str, Any]:
    """Outbound-only settings to limit spend on voicemail, silence, and long calls."""
    controls: dict[str, Any] = {
        "maxDurationSeconds": config.VAPI_MAX_CALL_DURATION_SECONDS,
        "silenceTimeoutSeconds": config.VAPI_SILENCE_TIMEOUT_SECONDS,
    }
    if config.VAPI_VOICEMAIL_DETECTION_ENABLED:
        controls["voicemailDetection"] = {
            "provider": "vapi",
            "backoffPlan": {
                "maxRetries": 5,
                "startAtSeconds": 2,
                "frequencySeconds": 2.5,
            },
            "beepMaxAwaitSeconds": config.VAPI_VOICEMAIL_BEEP_MAX_AWAIT_SECONDS,
        }
        controls["voicemailMessage"] = config.VAPI_VOICEMAIL_MESSAGE
    return controls


def build_call_request_overrides() -> dict[str, Any]:
    """Fields allowed on POST /call assistantOverrides (not silence/voicemail — assistant-level only)."""
    return {"maxDurationSeconds": config.VAPI_MAX_CALL_DURATION_SECONDS}


def build_assistant_payload(
    server_url: str | None = None,
    tool_ids: list[str] | None = None,
    *,
    direction: str = "outbound",
) -> dict[str, Any]:
    """Build Vapi assistant config. Both directions use assistant-speaks-first; inbound waits ~1s before hello."""
    url = server_url or webhook_url()
    inbound = direction == "inbound"
    system_prompt = SYSTEM_PROMPT + build_inbound_context() if inbound else SYSTEM_PROMPT

    model: dict[str, Any] = {
        "provider": "openai",
        "model": "gpt-4.1",
        "temperature": 0.88,
        "maxTokens": 80,
        "messages": [{"role": "system", "content": system_prompt}],
    }
    if tool_ids:
        model["toolIds"] = tool_ids
    else:
        model["tools"] = [build_book_appointment_tool(url)]

    server_block: dict[str, Any] = {"url": url}
    if config.VAPI_WEBHOOK_SECRET:
        server_block["secret"] = config.VAPI_WEBHOOK_SECRET

    if inbound:
        first_message = config.VAPI_INBOUND_FIRST_MESSAGE
        first_message_mode = "assistant-speaks-first"
        response_delay = config.VAPI_INBOUND_RESPONSE_DELAY_SECONDS
        start_wait = config.VAPI_INBOUND_START_WAIT_SECONDS
        name = f"{config.VAPI_INBOUND_BOT_NAME} — {config.BUSINESS_NAME} Inbound Callback"
        llm_request_delay = config.VAPI_INBOUND_LLM_REQUEST_DELAY_SECONDS
    else:
        first_message = build_assistant_first_message_template(DEFAULT_CAMPAIGN_ID)
        first_message_mode = "assistant-speaks-first"
        response_delay = config.VAPI_RESPONSE_DELAY_SECONDS
        start_wait = config.VAPI_START_WAIT_SECONDS
        name = f"{config.BUSINESS_NAME} Warm Follow-Up"
        llm_request_delay = config.VAPI_LLM_REQUEST_DELAY_SECONDS

    transcriber_endpointing = (
        config.VAPI_INBOUND_TRANSCRIBER_ENDPOINTING if inbound else 200
    )

    payload: dict[str, Any] = {
        "name": name,
        "firstMessage": first_message,
        "firstMessageMode": first_message_mode,
        "responseDelaySeconds": response_delay,
        "llmRequestDelaySeconds": llm_request_delay,
        "startSpeakingPlan": _build_start_speaking_plan(
            wait_seconds=start_wait,
            inbound=inbound,
        ),
        "backgroundSound": "off",
        "backgroundDenoisingEnabled": False,
        "model": model,
        "voice": build_voice_config(),
        "transcriber": _build_transcriber_config(endpointing=transcriber_endpointing),
        "recordingEnabled": True,
        "server": server_block,
        "serverMessages": ["end-of-call-report", "tool-calls"],
        "endCallFunctionEnabled": True,
        "analysisPlan": _analysis_plan(),
    }
    if inbound:
        payload["maxDurationSeconds"] = config.VAPI_MAX_CALL_DURATION_SECONDS
    else:
        payload.update(build_outbound_cost_controls())
    return payload


def build_inbound_assistant_payload(
    server_url: str | None = None,
    tool_ids: list[str] | None = None,
) -> dict[str, Any]:
    return build_assistant_payload(server_url, tool_ids, direction="inbound")


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

    def update_phone_number(self, phone_number_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", f"/phone-number/{phone_number_id}", json=payload)

    def sync_inbound_phone_number(self, inbound_assistant_id: str) -> dict[str, Any]:
        """Point the Twilio/Vapi number at the inbound assistant (outbound dials keep their own assistantId)."""
        phone_number_id = config.VAPI_PHONE_NUMBER_ID
        if not phone_number_id:
            raise ValueError("VAPI_PHONE_NUMBER_ID not configured")
        return self.update_phone_number(
            phone_number_id,
            {"assistantId": inbound_assistant_id},
        )

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
        campaign_id: str | None = None,
    ) -> dict[str, Any]:
        assistant_id = config.VAPI_ASSISTANT_ID
        if not assistant_id:
            raise ValueError("VAPI_ASSISTANT_ID not configured — run scripts/create_assistant.py first")

        campaign = campaign_id or DEFAULT_CAMPAIGN_ID
        first_message = build_outbound_first_message(campaign, first_name)
        system_prompt = build_outbound_system_prompt(campaign)

        payload = {
            "assistantId": assistant_id,
            "phoneNumberId": config.VAPI_PHONE_NUMBER_ID,
            "customer": {
                "number": phone,
                "name": first_name or "there",
            },
            "assistantOverrides": {
                "recordingEnabled": True,
                "firstMessage": first_message,
                "model": {
                    "messages": [{"role": "system", "content": system_prompt}],
                },
                "voice": build_voice_config(),
                "variableValues": {
                    "firstName": first_name or "there",
                    "contactId": contact_id,
                    "queueId": str(queue_id or ""),
                    "preCallBrief": brief,
                    "loanCampaign": campaign,
                },
                **build_call_request_overrides(),
            },
            "metadata": {
                "contactId": contact_id,
                "queueId": queue_id,
                "loanCampaign": campaign,
            },
            **build_call_request_overrides(),
        }
        # Primary endpoint per Vapi docs; /call/phone kept as fallback for older accounts
        try:
            return self._request("POST", "/call", json=payload)
        except requests.HTTPError:
            return self._request("POST", "/call/phone", json={**payload, "type": "outboundPhoneCall"})

    def get_call(self, call_id: str) -> dict[str, Any]:
        return self._request("GET", f"/call/{call_id}")
