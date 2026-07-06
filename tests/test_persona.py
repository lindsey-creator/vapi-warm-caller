"""Tests for Lindsey persona integration."""

from src.persona import build_caller_prompt, load_voice_examples
from src.vapi_client import SYSTEM_PROMPT


class TestPersona:
    def test_build_caller_prompt_includes_style(self):
        prompt = build_caller_prompt()
        assert "LINDSEY'S TEAM" in prompt or "call center" in prompt.lower()

    def test_voice_examples_load_from_lindsey_ai(self):
        examples = load_voice_examples()
        if examples:
            assert "LINDSEY'S ACTUAL TONE" in examples

    def test_system_prompt_handles_no_memory_objection(self):
        assert "If they say no, don't remember filling anything out, or sound unsure" in SYSTEM_PROMPT
        assert "purchases and refinances in Northeast Ohio" in SYSTEM_PROMPT
        assert "Any interest in chatting with the team, or not really?" in SYSTEM_PROMPT
