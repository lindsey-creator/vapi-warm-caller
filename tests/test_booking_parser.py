"""Tests for booking datetime parsing."""

from datetime import datetime
from zoneinfo import ZoneInfo

from src.gcal_client import _parse_preferred_datetime, parse_booking_tool_args


class TestParseBookingToolArgs:
    def test_normalizes_args(self):
        result = parse_booking_tool_args(
            {
                "preferred_date": "2026-07-10",
                "preferred_time": "2:00 PM",
                "timezone": "America/New_York",
                "notes": "Interested in DSCR",
            }
        )
        assert result["preferred_date"] == "2026-07-10"
        assert result["preferred_time"] == "2:00 PM"
        assert result["timezone"] == "America/New_York"
        assert result["notes"] == "Interested in DSCR"

    def test_defaults_timezone(self):
        result = parse_booking_tool_args({"preferred_date": "2026-07-10", "preferred_time": "10am"})
        assert result["timezone"]  # falls back to config default


class TestParsePreferredDatetime:
    def test_12h_format(self):
        tz = ZoneInfo("America/New_York")
        dt = _parse_preferred_datetime("2026-07-10", "2:30 PM", tz)
        assert dt is not None
        assert dt.hour == 14
        assert dt.minute == 30

    def test_24h_format(self):
        tz = ZoneInfo("America/New_York")
        dt = _parse_preferred_datetime("2026-07-10", "14:00", tz)
        assert dt is not None
        assert dt.hour == 14

    def test_invalid_date_returns_none(self):
        tz = ZoneInfo("America/New_York")
        assert _parse_preferred_datetime("not-a-date", "2 PM", tz) is None

    def test_invalid_time_returns_none(self):
        tz = ZoneInfo("America/New_York")
        assert _parse_preferred_datetime("2026-07-10", "noonish", tz) is None
