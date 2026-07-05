"""Lindsey voice/style layer — pulled from lindsey-ai persona (Claude-generated)."""

from __future__ import annotations

import json
from pathlib import Path

from src import config

VOICE_STYLE = """
COMMUNICATION STYLE (from Lindsey's actual voice — match this on calls):
- Short, direct, no fluff. Get to the point fast.
- Casual, like talking to a smart friend. Never corporate, never sounds scripted.
- Warm but confident — you're following up because they reached out, not begging.
- One question at a time. Don't monologue.
- Never quote specific rates or payment numbers — "depends on your situation, team walks through it."
- If they ask if you're AI, be honest and offer a human callback.
"""


def load_voice_examples(path: str | None = None, limit: int = 5) -> str:
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
                    lines.append(f'- Context: {ctx[:80]}… → "{msg[:120]}"')
    except (OSError, json.JSONDecodeError):
        return ""
    if not lines:
        return ""
    return "VOICE EXAMPLES (style reference only — adapt for phone, don't read verbatim):\n" + "\n".join(
        lines
    )


def build_caller_prompt() -> str:
    examples = load_voice_examples()
    parts = [VOICE_STYLE.strip()]
    if examples:
        parts.append(examples)
    return "\n\n".join(parts)
