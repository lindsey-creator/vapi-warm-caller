"""Tests for loan campaign resolution and prompt content."""

from src.loan_campaigns import (
    build_outbound_first_message,
    build_outbound_system_prompt,
    resolve_campaign_from_tags,
)
from src.vapi_client import VapiClient


class TestCampaignResolution:
    def test_purchase_tag(self):
        assert resolve_campaign_from_tags({"form-fill", "loan-purchase"}) == "purchase"

    def test_refi_tag(self):
        assert resolve_campaign_from_tags({"loan-refi"}) == "refi"

    def test_dscr_tag(self):
        assert resolve_campaign_from_tags({"loan-dscr"}) == "dscr"

    def test_dscr_wins_over_purchase(self):
        assert resolve_campaign_from_tags({"loan-purchase", "loan-dscr"}) == "dscr"

    def test_default_without_loan_tag(self):
        assert resolve_campaign_from_tags({"form-fill"}) == "general"


class TestCampaignPrompts:
    def test_purchase_first_message(self):
        msg = build_outbound_first_message("purchase", "Jane")
        assert "Jane" in msg
        assert "buying a home" in msg.lower()

    def test_dscr_system_prompt_mentions_investor(self):
        prompt = build_outbound_system_prompt("dscr")
        assert "DSCR" in prompt or "investor" in prompt.lower()
        assert "rental" in prompt.lower()

    def test_refi_no_memory_fallback(self):
        prompt = build_outbound_system_prompt("refi")
        assert "refinance" in prompt.lower()


class TestCreateCallOverrides:
    def test_create_call_payload_includes_campaign(self, monkeypatch):
        monkeypatch.setattr("src.vapi_client.config.VAPI_ASSISTANT_ID", "asst-test")
        monkeypatch.setattr("src.vapi_client.config.VAPI_PHONE_NUMBER_ID", "phone-test")

        captured: dict = {}

        def fake_request(self, method, path, **kwargs):
            captured.update(kwargs.get("json", {}))
            return {"id": "call-1"}

        monkeypatch.setattr(VapiClient, "_request", fake_request)

        client = VapiClient(api_key="test-key")
        client.create_call(
            phone="+15551234567",
            contact_id="c1",
            first_name="Alex",
            campaign_id="purchase",
        )

        overrides = captured["assistantOverrides"]
        assert "buying a home" in overrides["firstMessage"].lower()
        assert overrides["variableValues"]["loanCampaign"] == "purchase"
        assert captured["metadata"]["loanCampaign"] == "purchase"
        system = overrides["model"]["messages"][0]["content"]
        assert "pre-approved" in system.lower()
