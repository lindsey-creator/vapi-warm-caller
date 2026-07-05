"""Tests for trigger matching and monitor logic."""

from unittest.mock import MagicMock

from src.compliance import has_exclusion_tag, match_trigger
from src.triggers import TriggerMonitor


class TestTriggerMatching:
    def test_form_fill_matches(self):
        assert match_trigger({"form-fill"}, ("form-fill",))

    def test_exclusion_blocks(self):
        assert has_exclusion_tag({"form-fill", "call-booked"})

    def test_hot_lead_matches(self):
        assert match_trigger({"hot-lead"}, ("hot-lead",))


class TestTriggerMonitor:
    def test_poll_enqueues_eligible_contact(self, tmp_path):
        store = __import__("src.store", fromlist=["Store"]).Store(str(tmp_path / "t.db"))
        ghl = MagicMock()
        ghl.search_contacts_by_tag.return_value = [
            {
                "id": "contact-abc",
                "firstName": "Jane",
                "lastName": "Doe",
                "phone": "+15551234567",
                "email": "jane@example.com",
                "tags": ["form-fill"],
            }
        ]
        ghl.contact_tags.return_value = {"form-fill"}
        ghl.contact_phone.return_value = "+15551234567"
        ghl.contact_timezone.return_value = "America/New_York"
        ghl.build_brief.return_value = "Test brief"

        monitor = TriggerMonitor(ghl=ghl, store=store)
        queued = monitor.poll()
        assert len(queued) == 1
        pending = store.get_pending_queue()
        assert pending[0]["contact_id"] == "contact-abc"

    def test_poll_skips_excluded_contacts(self, tmp_path):
        store = __import__("src.store", fromlist=["Store"]).Store(str(tmp_path / "t2.db"))
        ghl = MagicMock()
        ghl.search_contacts_by_tag.return_value = [
            {
                "id": "contact-xyz",
                "phone": "+15559876543",
                "tags": ["form-fill", "call-booked"],
            }
        ]
        ghl.contact_tags.return_value = {"form-fill", "call-booked"}

        monitor = TriggerMonitor(ghl=ghl, store=store)
        queued = monitor.poll()
        assert len(queued) == 0

    def test_poll_deduplicates_across_triggers(self, tmp_path):
        store = __import__("src.store", fromlist=["Store"]).Store(str(tmp_path / "t3.db"))
        ghl = MagicMock()
        contact = {
            "id": "dup-contact",
            "phone": "+15551112222",
            "tags": ["form-fill", "hot-lead"],
            "firstName": "Dup",
        }
        ghl.search_contacts_by_tag.return_value = [contact]
        ghl.contact_tags.return_value = {"form-fill", "hot-lead"}
        ghl.contact_phone.return_value = "+15551112222"
        ghl.contact_timezone.return_value = ""
        ghl.build_brief.return_value = "brief"

        monitor = TriggerMonitor(ghl=ghl, store=store)
        queued = monitor.poll()
        assert len(queued) == 1
