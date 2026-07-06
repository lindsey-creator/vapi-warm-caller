"""Tests for inbound lead webhook from Conrad Team."""

from unittest.mock import MagicMock

from src.inbound_trigger import ingest_inbound_lead, resolve_trigger_id


class TestResolveTrigger:
    def test_by_trigger_id(self):
        assert resolve_trigger_id({"trigger_id": "form-fill"}) == "form-fill"

    def test_by_tag(self):
        assert resolve_trigger_id({"tags": ["hot-lead"]}) == "hot-lead"


class TestIngestInbound:
    def test_queues_lead(self, tmp_path):
        store = __import__("src.store", fromlist=["Store"]).Store(str(tmp_path / "in.db"))
        ghl = MagicMock()
        ghl.upsert_contact.return_value = {"id": "lindsey-contact-1", "tags": ["form-fill"]}

        result = ingest_inbound_lead(
            {
                "firstName": "Jane",
                "lastName": "Doe",
                "phone": "+15551234567",
                "email": "jane@example.com",
                "tags": ["form-fill"],
                "source_contact_id": "conrad-abc123",
                "source_sub_account": "The Conrad Team",
            },
            ghl=ghl,
            store=store,
        )
        assert result["ok"] is True
        assert result["queued"] is True
        assert result["contact_id"] == "lindsey-contact-1"

    def test_rejects_exclusion_tag(self, tmp_path):
        store = __import__("src.store", fromlist=["Store"]).Store(str(tmp_path / "in2.db"))
        ghl = MagicMock()
        result = ingest_inbound_lead(
            {"phone": "+15551234567", "tags": ["form-fill", "dnc"]},
            ghl=ghl,
            store=store,
        )
        assert result["ok"] is False
        ghl.upsert_contact.assert_not_called()

    def test_requires_phone(self, tmp_path):
        store = __import__("src.store", fromlist=["Store"]).Store(str(tmp_path / "in3.db"))
        result = ingest_inbound_lead({"tags": ["form-fill"]}, ghl=MagicMock(), store=store)
        assert result["error"] == "phone is required"
