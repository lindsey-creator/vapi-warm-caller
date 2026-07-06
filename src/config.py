"""Central configuration: env vars, trigger definitions, compliance policy."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Tags that prove consent to receive a call (form fill = primary consent record).
CONSENT_TAGS: frozenset[str] = frozenset(
    {
        "form-fill",
        "email-engaged-3plus",
        "quiz-start",
        "quiz-complete",
        "webinar-attended",
        "hot-lead",
    }
)

# Tags that block dialing regardless of trigger match.
GLOBAL_EXCLUSION_TAGS: frozenset[str] = frozenset(
    {
        "call-booked",
        "email-replied",
        "contacted",
        "dnc",
        "do-not-call",
    }
)

# Outcome tags applied after calls.
OUTCOME_TAGS: dict[str, str] = {
    "booked": "call-booked",
    "not_ready": "not-ready-nurture",
    "no_answer": "call-no-answer",
    "voicemail": "call-voicemail",
    "wrong_number": "call-wrong-number",
    "needs_human": "needs-human-followup",
    "dnc_requested": "dnc",
}


@dataclass(frozen=True)
class TriggerDef:
    id: str
    name: str
    required_tags: tuple[str, ...]
    exclusion_tags: tuple[str, ...] = field(default_factory=lambda: tuple(GLOBAL_EXCLUSION_TAGS))
    priority: int = 5  # lower = higher priority


TRIGGERS: tuple[TriggerDef, ...] = (
    TriggerDef(
        id="hot-lead",
        name="Hot Lead",
        required_tags=("hot-lead",),
        priority=0,
    ),
    TriggerDef(
        id="form-fill",
        name="Form Fill Follow-Up",
        required_tags=("form-fill",),
        priority=1,
    ),
    TriggerDef(
        id="email-engaged",
        name="Email Engaged 3+ Opens",
        required_tags=("email-engaged-3plus",),
        priority=2,
    ),
    TriggerDef(
        id="quiz-start",
        name="Quiz Started",
        required_tags=("quiz-start",),
        priority=3,
    ),
    TriggerDef(
        id="quiz-complete",
        name="Quiz Completed",
        required_tags=("quiz-complete",),
        priority=4,
    ),
    TriggerDef(
        id="webinar",
        name="Webinar Attended",
        required_tags=("webinar-attended",),
        priority=5,
    ),
)

# Attempt policy (env-tunable)
max_attempts_per_lead: int = int(os.getenv("MAX_ATTEMPTS_PER_LEAD", "3"))
min_hours_between_attempts: int = int(os.getenv("MIN_HOURS_BETWEEN_ATTEMPTS", "24"))

# Calling hours (lead-local)
calling_hour_start: int = 9
calling_hour_end: int = 20

# Env-backed settings
GHL_API_TOKEN: str = os.getenv("GHL_API_TOKEN", "")
GHL_LOCATION_ID: str = os.getenv("GHL_LOCATION_ID", "")
GHL_NURTURE_WORKFLOW_ID: str = os.getenv("GHL_NURTURE_WORKFLOW_ID", "")

# Dedicated Lindsey sub-account — all leads, tags, workflows, and AI activity live here.
GHL_INBOUND_WEBHOOK_SECRET: str = os.getenv("GHL_INBOUND_WEBHOOK_SECRET", "")
TRIGGER_MODE: str = os.getenv("TRIGGER_MODE", "poll").lower()  # poll | webhook | both

VAPI_API_KEY: str = os.getenv("VAPI_API_KEY", "")
VAPI_PHONE_NUMBER_ID: str = os.getenv("VAPI_PHONE_NUMBER_ID", "")
VAPI_ASSISTANT_ID: str = os.getenv("VAPI_ASSISTANT_ID", "")
VAPI_WEBHOOK_SECRET: str = os.getenv("VAPI_WEBHOOK_SECRET", "")
VAPI_VOICE_PROVIDER: str = os.getenv("VAPI_VOICE_PROVIDER", "vapi")
VAPI_VOICE_ID: str = os.getenv("VAPI_VOICE_ID", "Emma")
VAPI_VOICE_VERSION: int = int(os.getenv("VAPI_VOICE_VERSION", "2"))
# Optional ElevenLabs tuning when VAPI_VOICE_PROVIDER=11labs (requires key in Vapi dashboard)
VAPI_ELEVENLABS_MODEL: str = os.getenv("VAPI_ELEVENLABS_MODEL", "eleven_turbo_v2_5")
VAPI_ELEVENLABS_STABILITY: float = float(os.getenv("VAPI_ELEVENLABS_STABILITY", "0.42"))
VAPI_ELEVENLABS_SIMILARITY: float = float(os.getenv("VAPI_ELEVENLABS_SIMILARITY", "0.78"))
VAPI_ELEVENLABS_STYLE: float = float(os.getenv("VAPI_ELEVENLABS_STYLE", "0.42"))
VAPI_ELEVENLABS_SPEED: float = float(os.getenv("VAPI_ELEVENLABS_SPEED", "0.97"))
VAPI_ELEVENLABS_USE_SPEAKER_BOOST: bool = os.getenv("VAPI_ELEVENLABS_USE_SPEAKER_BOOST", "true").lower() == "true"
VAPI_ELEVENLABS_STREAMING_LATENCY: int = int(os.getenv("VAPI_ELEVENLABS_STREAMING_LATENCY", "4"))
VAPI_RESPONSE_DELAY_SECONDS: float = float(os.getenv("VAPI_RESPONSE_DELAY_SECONDS", "0.25"))
VAPI_LLM_REQUEST_DELAY_SECONDS: float = float(os.getenv("VAPI_LLM_REQUEST_DELAY_SECONDS", "0.05"))
VAPI_START_WAIT_SECONDS: float = float(os.getenv("VAPI_START_WAIT_SECONDS", "0.45"))

# Inbound callbacks (someone dials back the outbound number) — separate assistant on the phone number.
VAPI_INBOUND_ASSISTANT_ID: str = os.getenv("VAPI_INBOUND_ASSISTANT_ID", "")
VAPI_INBOUND_START_WAIT_SECONDS: float = float(os.getenv("VAPI_INBOUND_START_WAIT_SECONDS", "0.45"))
VAPI_INBOUND_RESPONSE_DELAY_SECONDS: float = float(
    os.getenv("VAPI_INBOUND_RESPONSE_DELAY_SECONDS", "0.08")
)
VAPI_INBOUND_LLM_REQUEST_DELAY_SECONDS: float = float(
    os.getenv("VAPI_INBOUND_LLM_REQUEST_DELAY_SECONDS", "0")
)
VAPI_INBOUND_TRANSCRIBER_ENDPOINTING: int = int(
    os.getenv("VAPI_INBOUND_TRANSCRIBER_ENDPOINTING", "100")
)
VAPI_INBOUND_FIRST_MESSAGE: str = os.getenv(
    "VAPI_INBOUND_FIRST_MESSAGE",
    "Hey, hello?",
)
VAPI_INBOUND_BOT_NAME: str = os.getenv("VAPI_INBOUND_BOT_NAME", "Alex")

WEBHOOK_BASE_URL: str = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")

GCAL_CALENDAR_ID: str = os.getenv("GCAL_CALENDAR_ID", "")
GCAL_CREDENTIALS_PATH: str = os.getenv(
    "GCAL_CREDENTIALS_PATH", str(BASE_DIR / "credentials" / "service_account.json")
)
GCAL_TIMEZONE: str = os.getenv("GCAL_TIMEZONE", "America/New_York")
GCAL_SLOT_DURATION_MINUTES: int = int(os.getenv("GCAL_SLOT_DURATION_MINUTES", "30"))
GCAL_BOOKING_HORIZON_DAYS: int = int(os.getenv("GCAL_BOOKING_HORIZON_DAYS", "14"))

MAX_CONCURRENT_CALLS: int = int(os.getenv("MAX_CONCURRENT_CALLS", "2"))
POLL_INTERVAL_SECONDS: int = int(os.getenv("POLL_INTERVAL_SECONDS", "300"))

DATABASE_PATH: str = os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "caller.db"))

SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
SUMMARY_EMAIL_TO: str = os.getenv("SUMMARY_EMAIL_TO", "")

BUSINESS_NAME: str = os.getenv("BUSINESS_NAME", "Conrad Mortgage")

# Optional: Lindsey voice examples from lindsey-ai project (Claude-generated persona)
_default_voice = Path.home() / "Downloads" / "lindsey-ai" / "data" / "voice_examples.jsonl"
LINDSEY_VOICE_EXAMPLES_PATH: str = os.getenv(
    "LINDSEY_VOICE_EXAMPLES_PATH",
    str(_default_voice) if _default_voice.exists() else "",
)

GHL_BASE_URL = "https://services.leadconnectorhq.com"
VAPI_BASE_URL = "https://api.vapi.ai"
VAPI_MAX_CALL_DURATION_SECONDS: int = int(os.getenv("VAPI_MAX_CALL_DURATION_SECONDS", "180"))
# Outbound dead-air controls (Vapi default silence timeout is 30s)
VAPI_SILENCE_TIMEOUT_SECONDS: int = int(os.getenv("VAPI_SILENCE_TIMEOUT_SECONDS", "12"))
VAPI_VOICEMAIL_DETECTION_ENABLED: bool = (
    os.getenv("VAPI_VOICEMAIL_DETECTION_ENABLED", "true").lower() == "true"
)
VAPI_VOICEMAIL_BEEP_MAX_AWAIT_SECONDS: int = int(
    os.getenv("VAPI_VOICEMAIL_BEEP_MAX_AWAIT_SECONDS", "15")
)
VAPI_VOICEMAIL_MESSAGE: str = os.getenv(
    "VAPI_VOICEMAIL_MESSAGE",
    (
        "Hi, it's Lindsey's team at {business} — you reached out online about mortgages. "
        "We'll try you again soon, or call us back when it's convenient."
    ).format(business=BUSINESS_NAME),
)
