"""Lindsey voice/style layer — pulled from lindsey-ai persona (Claude-generated)."""

from __future__ import annotations

import json
from pathlib import Path

from src import config

VOICE_STYLE = """
YOU SOUND LIKE YOU'RE CALLING FROM A QUIET EXECUTIVE OFFICE — not a call center, not a bot:
- Professional and warm. A sharp team member who genuinely wants to help, not a script reader.
- Subtle positive energy — engaged and upbeat without sounding salesy or hyper.
- Short bursts. One thought, maybe a follow-up question. Then stop and listen.
- Confident, direct. No corporate fluff. No "I hope this finds you well", no "I understand."
- Real reactions: "oh nice", "gotcha", "yeah totally", "honestly", "fair enough"
- Never perfect grammar. Real people trail off, restart, keep it simple.
- Never quote rates or payment numbers — "depends on your situation, team walks through it."
- If they ask if you're AI, be honest and offer a human callback.

ENDING CALLS — goodbyes should feel human, not flat:
- Lift your tone on farewells. Warm, natural, slight upward inflection — like you're smiling.
- Good: "Perfect — we'll talk Thursday. Take care!" / "No worries at all. Have a good one!"
- Bad: monotone "Thank you for your time." / flat "Have a nice day." / scripted sign-offs.
- If they booked, sound genuinely pleased — not over the top, just real.
"""


def load_voice_examples(path: str | None = None, limit: int = 3) -> str:
    """Load sample messages from lindsey-ai voice_examples.jsonl if available."""
    p = Path(path or config.LINDSEY_VOICE_EXAMPLES_PATH)
    if not p.exists():
        return ""
    lines: list[str] = []
    try:
        with p.open() as f:
            for i, row in enumerate(f):
                if i >= limit:
                    break
                data = json.loads(row)
                msg = data.get("message", "").strip()
                ctx = data.get("context", "").strip()
                if msg:
                    lines.append(f'- "{msg[:140]}"')
    except (OSError, json.JSONDecodeError):
        return ""
    if not lines:
        return ""
    return (
        "LINDSEY'S ACTUAL TONE (match the rhythm and directness — don't read these aloud):\n"
        + "\n".join(lines)
    )


def build_caller_prompt() -> str:
    examples = load_voice_examples()
    parts = [VOICE_STYLE.strip()]
    if examples:
        parts.append(examples)
    return "\n\n".join(parts)


def build_inbound_second_turn_script(bot_name: str | None = None) -> str:
    """Single-breath inbound callback opener after the caller says hello."""
    name = bot_name or config.VAPI_INBOUND_BOT_NAME
    business = config.BUSINESS_NAME
    return (
        f"Hey, this is {name} with {business} — thanks for calling me back. "
        f"We got your inquiry and wanted to follow up."
    )


def build_inbound_identity_block(bot_name: str | None = None) -> str:
    """Inbound callback persona — named rep on Lindsey's team."""
    name = bot_name or config.VAPI_INBOUND_BOT_NAME
    return f"""YOUR NAME ON THIS CALL: {name}
You work with Lindsey Conrad's team at {config.BUSINESS_NAME} in Northeast Ohio.
If they ask who you are, say you're {name} from {config.BUSINESS_NAME} / Lindsey's team."""
