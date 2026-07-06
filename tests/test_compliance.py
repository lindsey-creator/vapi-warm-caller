"""Tests for compliance gate."""

from datetime import datetime, timedelta, timezone

import pytest

from src.compliance import (
    check_attempt_policy,
    evaluate_contact,
    has_consent,
    has_exclusion_tag,
    is_within_calling_hours,
    match_trigger,
)
from src.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "test.db"))


class TestConsent:
    def test_form_fill_has_consent(self):
        assert has_consent({"form-fill"})

    def test_no_tags_no_consent(self):
        assert not has_consent(set())

    def test_quiz_start_has_consent(self):
        assert has_consent({"quiz-start"})

    def test_exclusion_tag_blocks(self):
        assert has_exclusion_tag({"call-booked"})
        assert has_exclusion_tag({"dnc"})


class TestCallingHours:
    def test_within_hours_eastern(self):
        # 2 PM Eastern = 18:00 UTC (during EDT)
        now = datetime(2026, 7, 5, 18, 0, tzinfo=timezone.utc)
        assert is_within_calling_hours("America/New_York", now=now)

    def test_outside_hours_late_night(self):
        now = datetime(2026, 7, 5, 3, 0, tzinfo=timezone.utc)
        assert not is_within_calling_hours("America/New_York", now=now)

    def test_invalid_tz_falls_back(self):
        now = datetime(2026, 7, 5, 15, 0, tzinfo=timezone.utc)
        assert is_within_calling_hours("Invalid/Timezone", now=now)


class TestAttemptPolicy:
    def test_first_attempt_allowed(self, store):
        result = check_attempt_policy("contact-1", store)
        assert result.allowed

    def test_max_attempts_blocked(self, store):
        for i in range(3):
            store.record_attempt(contact_id="contact-1", outcome="no_answer")
        result = check_attempt_policy("contact-1", store)
        assert not result.allowed
        assert "max attempts" in result.reason

    def test_min_hours_between_attempts(self, store):
        store.record_attempt(contact_id="contact-2", outcome="no_answer")
        result = check_attempt_policy("contact-2", store)
        assert not result.allowed
        assert "24h" in result.reason


class TestEvaluateContact:
    def test_fails_closed_no_contact(self, store):
        result = evaluate_contact(None, store)
        assert not result.allowed
        assert "fails closed" in result.reason

    def test_no_consent_blocked(self, store):
        contact = {"id": "c1", "phone": "+15551234567", "tags": []}
        result = evaluate_contact(contact, store)
        assert not result.allowed

    def test_dnd_blocked(self, store):
        contact = {
            "id": "c1",
            "phone": "+15551234567",
            "tags": ["form-fill"],
            "dnd": True,
        }
        result = evaluate_contact(contact, store)
        assert not result.allowed

    def test_inactive_call_dnd_allowed(self, store):
        now = datetime(2026, 7, 5, 18, 0, tzinfo=timezone.utc)
        contact = {
            "id": "c1",
            "phone": "+15551234567",
            "tags": ["form-fill"],
            "dnd": False,
            "dndSettings": {"Call": {"status": "inactive"}},
            "timezone": "America/New_York",
        }
        result = evaluate_contact(contact, store, now=now)
        assert result.allowed

    def test_valid_contact_allowed(self, store):
        now = datetime(2026, 7, 5, 18, 0, tzinfo=timezone.utc)
        contact = {
            "id": "c1",
            "phone": "+15551234567",
            "tags": ["form-fill"],
            "timezone": "America/New_York",
        }
        result = evaluate_contact(contact, store, now=now)
        assert result.allowed


class TestMatchTrigger:
    def test_required_tags_match(self):
        assert match_trigger({"form-fill", "other"}, ("form-fill",))

    def test_missing_required_tag(self):
        assert not match_trigger({"email-engaged-3plus"}, ("form-fill",))
