"""Google Calendar: find free slots and book consultations."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build

from src import config

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


class GCalClient:
    def __init__(
        self,
        calendar_id: str | None = None,
        credentials_path: str | None = None,
    ) -> None:
        self.calendar_id = calendar_id or config.GCAL_CALENDAR_ID
        cred_path = credentials_path or config.GCAL_CREDENTIALS_PATH
        creds = service_account.Credentials.from_service_account_file(cred_path, scopes=SCOPES)
        self.service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    def find_free_slot(
        self,
        preferred_date: str,
        preferred_time: str,
        timezone: str | None = None,
    ) -> tuple[str, str] | None:
        """Return (start_iso, end_iso) for the nearest available slot."""
        tz = ZoneInfo(timezone or config.GCAL_TIMEZONE)
        start = _parse_preferred_datetime(preferred_date, preferred_time, tz)
        if start is None:
            start = datetime.now(tz) + timedelta(days=1)
            start = start.replace(hour=10, minute=0, second=0, microsecond=0)

        duration = timedelta(minutes=config.GCAL_SLOT_DURATION_MINUTES)
        horizon = timedelta(days=config.GCAL_BOOKING_HORIZON_DAYS)

        candidate = start
        end_horizon = start + horizon
        while candidate < end_horizon:
            slot_end = candidate + duration
            if self._is_slot_free(candidate, slot_end):
                return (
                    candidate.isoformat(),
                    slot_end.isoformat(),
                )
            candidate += timedelta(minutes=30)
        return None

    def _is_slot_free(self, start: datetime, end: datetime) -> bool:
        body = {
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "timeZone": str(start.tzinfo),
            "items": [{"id": self.calendar_id}],
        }
        result = self.service.freebusy().query(body=body).execute()
        busy = result.get("calendars", {}).get(self.calendar_id, {}).get("busy", [])
        return len(busy) == 0

    def book_event(
        self,
        *,
        contact_name: str,
        contact_email: str,
        slot_start: str,
        slot_end: str,
        brief: str = "",
        timezone: str | None = None,
    ) -> dict[str, Any]:
        tz = timezone or config.GCAL_TIMEZONE
        description = brief or "Warm follow-up consultation booked via AI caller."
        event = {
            "summary": f"Consultation — {contact_name} ({config.BUSINESS_NAME})",
            "description": description,
            "start": {"dateTime": slot_start, "timeZone": tz},
            "end": {"dateTime": slot_end, "timeZone": tz},
        }
        if contact_email:
            event["attendees"] = [{"email": contact_email}]
        created = (
            self.service.events()
            .insert(calendarId=self.calendar_id, body=event, sendUpdates="all")
            .execute()
        )
        return created


def _parse_preferred_datetime(date_str: str, time_str: str, tz: ZoneInfo) -> datetime | None:
    try:
        date_part = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None

    normalized = time_str.strip().upper().replace(".", "")
    for fmt in ("%I:%M %p", "%I %p", "%H:%M"):
        try:
            time_part = datetime.strptime(normalized, fmt).time()
            return datetime.combine(date_part, time_part, tzinfo=tz)
        except ValueError:
            continue
    return None


def parse_booking_tool_args(args: dict[str, Any]) -> dict[str, str]:
    """Normalize Vapi tool-call arguments for booking."""
    return {
        "preferred_date": str(args.get("preferred_date", "")).strip(),
        "preferred_time": str(args.get("preferred_time", "")).strip(),
        "timezone": str(args.get("timezone") or config.GCAL_TIMEZONE).strip(),
        "notes": str(args.get("notes", "")).strip(),
    }
