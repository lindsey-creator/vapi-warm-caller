"""Tests for Lindsey persona integration."""

from src.persona import build_caller_prompt, load_voice_examples


class TestPersona:
    def test_build_caller_prompt_includes_style(self):
        prompt = build_caller_prompt()
        assert "Short, direct" in prompt

    def test_voice_examples_load_from_lindsey_ai(self):
        examples = load_voice_examples()
        # Auto-detects ~/Downloads/lindsey-ai if present
        if examples:
            assert "VOICE EXAMPLES" in examples
