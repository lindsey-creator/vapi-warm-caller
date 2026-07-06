"""Tests for post-call outcome classification."""

from src.postcall import classify_outcome


class TestClassifyOutcome:
    def test_silence_timed_out_is_no_answer(self):
        report = {"endedReason": "silence-timed-out", "analysis": {}}
        assert classify_outcome(report) == "no_answer"

    def test_voicemail_ended_reason(self):
        report = {"endedReason": "voicemail-reached", "analysis": {}}
        assert classify_outcome(report) == "voicemail"

    def test_structured_outcome_still_used(self):
        report = {
            "endedReason": "customer-ended-call",
            "analysis": {"structuredData": {"outcome": "booked"}},
        }
        assert classify_outcome(report) == "booked"
