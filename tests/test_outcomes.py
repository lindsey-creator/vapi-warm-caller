"""Tests for post-call outcome classification and note formatting."""

from src.postcall import classify_outcome, format_call_note


class TestClassifyOutcome:
    def test_structured_booked(self):
        report = {"analysis": {"structuredData": {"outcome": "booked"}}}
        assert classify_outcome(report) == "booked"

    def test_dnc_flag(self):
        report = {"analysis": {"structuredData": {"dnc_requested": True}}}
        assert classify_outcome(report) == "dnc_requested"

    def test_not_ready_from_summary(self):
        report = {"analysis": {"summary": "Lead said not ready, call back later"}}
        assert classify_outcome(report) == "not_ready"

    def test_dnc_from_summary(self):
        report = {"analysis": {"summary": "Asked to remove me from the list"}}
        assert classify_outcome(report) == "dnc_requested"

    def test_booked_from_summary(self):
        report = {"analysis": {"summary": "Successfully booked a consultation"}}
        assert classify_outcome(report) == "booked"

    def test_unknown_defaults_other(self):
        report = {"analysis": {"summary": "Short call, hung up"}}
        assert classify_outcome(report) == "other"


class TestFormatCallNote:
    def test_includes_outcome_and_cost(self):
        note = format_call_note(
            outcome="booked",
            transcript="user: hello\nassistant: hi",
            summary="Booked consult",
            recording_url="https://rec.example/1",
            cost=0.35,
        )
        assert "booked" in note
        assert "$0.35" in note
        assert "https://rec.example/1" in note
        assert "Transcript:" in note

    def test_truncates_long_transcript(self):
        note = format_call_note(outcome="other", transcript="x" * 5000)
        assert len(note) < 5000
