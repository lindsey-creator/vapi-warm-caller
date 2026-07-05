"""Tests for SQLite store."""

from src.store import Store


class TestStore:
    def test_enqueue_and_fetch(self, tmp_path):
        store = Store(str(tmp_path / "s.db"))
        qid = store.enqueue(
            contact_id="c1",
            trigger_id="form-fill",
            phone="+15551234567",
            first_name="Test",
        )
        assert qid is not None
        pending = store.get_pending_queue()
        assert len(pending) == 1
        assert pending[0]["contact_id"] == "c1"

    def test_duplicate_enqueue_ignored(self, tmp_path):
        store = Store(str(tmp_path / "s2.db"))
        args = dict(contact_id="c1", trigger_id="form-fill", phone="+1")
        assert store.enqueue(**args) is not None
        assert store.enqueue(**args) is None

    def test_active_call_tracking(self, tmp_path):
        store = Store(str(tmp_path / "s3.db"))
        store.register_active_call("call-1", "c1", 1)
        assert store.count_active_calls() == 1
        store.clear_active_call("call-1")
        assert store.count_active_calls() == 0

    def test_record_attempt_and_stats(self, tmp_path):
        store = Store(str(tmp_path / "s4.db"))
        store.record_attempt(
            contact_id="c1",
            outcome="booked",
            cost=0.42,
            duration_seconds=120,
        )
        assert store.get_attempt_count("c1") == 1
        stats = store.get_dashboard_stats()
        assert stats["calls_today"] >= 1
        assert stats["spend_today"] >= 0.42

    def test_booking_record(self, tmp_path):
        store = Store(str(tmp_path / "s5.db"))
        store.record_booking(
            contact_id="c1",
            vapi_call_id="call-99",
            slot_start="2026-07-10T14:00:00-04:00",
            slot_end="2026-07-10T14:30:00-04:00",
            gcal_event_id="evt-1",
        )
        stats = store.get_dashboard_stats()
        assert stats["booked_today"] >= 1

    def test_daily_summary_stats(self, tmp_path):
        store = Store(str(tmp_path / "s6.db"))
        store.record_attempt(contact_id="c2", outcome="needs_human", cost=0.15)
        summary = store.get_daily_summary_stats()
        assert summary["total_calls"] >= 1
        assert "needs_human" in summary["by_outcome"]
