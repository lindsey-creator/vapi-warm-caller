"""Compliance gate: consent, DNC, calling hours, attempt caps. Fails closed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from src import config
from src.ghl_client import GHLClient
from src.store import Store


@dataclass
class ComplianceResult:
    allowed: bool
    reason: str = ""


def has_consent(tags: set[str]) -> bool:
    return bool(tags & {t.lower() for t in config.CONSENT_TAGS})


def has_exclusion_tag(tags: set[str]) -> bool:
    return bool(tags & {t.lower() for t in config.GLOBAL_EXCLUSION_TAGS})


def is_within_calling_hours(
    tz_name: str | None,
    *,
    now: datetime | None = None,
    hour_start: int = config.calling_hour_start,
    hour_end: int = config.calling_hour_end,
) -> bool:
    now = now or datetime.now(timezone.utc)
    tz = _resolve_timezone(tz_name)
    local = now.astimezone(tz)
    return hour_start <= local.hour < hour_end


def _resolve_timezone(tz_name: str | None) -> ZoneInfo:
    if tz_name:
        try:
            return ZoneInfo(tz_name)
        except Exception:
            pass
    return ZoneInfo(config.GCAL_TIMEZONE)


def check_attempt_policy(contact_id: str, store: Store) -> ComplianceResult:
    count = store.get_attempt_count(contact_id)
    if count >= config.max_attempts_per_lead:
        return ComplianceResult(False, f"max attempts reached ({count})")

    last = store.get_last_attempt_time(contact_id)
    if last:
        elapsed = datetime.now(timezone.utc) - last.replace(tzinfo=timezone.utc)
        min_gap = timedelta(hours=config.min_hours_between_attempts)
        if elapsed < min_gap:
            return ComplianceResult(
                False,
                f"min {config.min_hours_between_attempts}h between attempts not met",
            )
    return ComplianceResult(True)


def evaluate_contact(
    contact: dict[str, Any] | None,
    store: Store,
    *,
    now: datetime | None = None,
) -> ComplianceResult:
    """Full gate check at dial time. Fails closed if contact can't be verified."""
    if contact is None:
        return ComplianceResult(False, "contact unavailable — fails closed")

    tags = GHLClient.contact_tags(contact)
    if not has_consent(tags):
        return ComplianceResult(False, "no consent tag")

    if has_exclusion_tag(tags):
        return ComplianceResult(False, "exclusion tag present")

    if GHLClient.is_dnd(contact):
        return ComplianceResult(False, "GHL DND flag set")

    phone = GHLClient.contact_phone(contact)
    if not phone:
        return ComplianceResult(False, "no phone number")

    tz = GHLClient.contact_timezone(contact) or config.GCAL_TIMEZONE
    if not is_within_calling_hours(tz, now=now):
        return ComplianceResult(False, "outside lead-local calling hours (9AM–8PM)")

    contact_id = contact.get("id") or contact.get("contactId") or ""
    if contact_id:
        attempt = check_attempt_policy(contact_id, store)
        if not attempt.allowed:
            return attempt

    return ComplianceResult(True)


def match_trigger(tags: set[str], trigger_required: tuple[str, ...]) -> bool:
    required = {t.lower() for t in trigger_required}
    return required.issubset(tags)
