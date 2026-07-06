"""Tests for Vapi assistant payload configuration."""

from src import config
from src.vapi_client import (
    build_assistant_payload,
    build_inbound_assistant_payload,
    build_outbound_cost_controls,
)


class TestAssistantPayload:
    def test_outbound_speaks_first(self):
        payload = build_assistant_payload()
        assert payload["firstMessageMode"] == "assistant-speaks-first"
        assert payload["startSpeakingPlan"]["waitSeconds"] == config.VAPI_START_WAIT_SECONDS
        assert "{{firstName}}" in payload["firstMessage"]
        assert payload["silenceTimeoutSeconds"] == config.VAPI_SILENCE_TIMEOUT_SECONDS
        assert payload["maxDurationSeconds"] == config.VAPI_MAX_CALL_DURATION_SECONDS
        if config.VAPI_VOICEMAIL_DETECTION_ENABLED:
            assert payload["voicemailDetection"]["provider"] == "vapi"
            assert payload["voicemailMessage"]

    def test_inbound_speaks_first_after_pickup_pause(self):
        payload = build_inbound_assistant_payload()
        assert payload["firstMessageMode"] == "assistant-speaks-first"
        assert payload["startSpeakingPlan"]["waitSeconds"] == config.VAPI_INBOUND_START_WAIT_SECONDS
        assert payload["startSpeakingPlan"]["smartEndpointingPlan"]["provider"] == "livekit"
        assert payload["startSpeakingPlan"]["customEndpointingRules"]
        assert payload["responseDelaySeconds"] == config.VAPI_INBOUND_RESPONSE_DELAY_SECONDS
        assert payload["llmRequestDelaySeconds"] == config.VAPI_INBOUND_LLM_REQUEST_DELAY_SECONDS
        assert payload["firstMessage"] == config.VAPI_INBOUND_FIRST_MESSAGE
        assert payload["transcriber"]["endpointing"] == config.VAPI_INBOUND_TRANSCRIBER_ENDPOINTING
        assert config.VAPI_INBOUND_BOT_NAME in payload["name"]
        assert "voicemailDetection" not in payload
        assert "silenceTimeoutSeconds" not in payload

    def test_outbound_transcriber_endpointing_default(self):
        payload = build_assistant_payload()
        assert payload["transcriber"]["endpointing"] == 200
        assert "customEndpointingRules" not in payload["startSpeakingPlan"]

    def test_outbound_cost_controls(self):
        controls = build_outbound_cost_controls()
        assert controls["silenceTimeoutSeconds"] == config.VAPI_SILENCE_TIMEOUT_SECONDS
        assert controls["maxDurationSeconds"] == config.VAPI_MAX_CALL_DURATION_SECONDS

    def test_inbound_system_prompt_mentions_callback_and_alex(self):
        payload = build_inbound_assistant_payload()
        system = payload["model"]["messages"][0]["content"]
        assert "INBOUND CALLBACK" in system
        assert config.VAPI_INBOUND_BOT_NAME in system
        assert "SECOND TURN" in system
        assert "hello?" in system.lower()
        assert "thanks for calling me back" in system.lower()
        assert "got your inquiry" in system.lower()
        assert "one continuous response" in system.lower()
