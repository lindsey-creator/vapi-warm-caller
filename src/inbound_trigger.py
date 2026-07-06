"""Handle one-way lead pushes from Conrad Team into the Lindsey sub-account."""

from __future__ import annotations

import logging
from typing import Any

from src import config
from src.compliance import has_exclusion_tag
from src.loan_campaigns import get_campaign, resolve_campaign_from_tags
from src.ghl_client import GHLClient
from src.store import Store

logger = logging.getLogger(__name__)

TRIGGER_BY_TAG = {t.required_tags[0]: t for t in config.TRIGGERS}
TRIGGER_BY_ID = {t.id: t for t in config.TRIGGERS}


def resolve_trigger_id(payload: dict[str, Any]) -> str | None:
    if payload.get("trigger_id") in TRIGGER_BY_ID:
        return payload["trigger_id"]
    tags = {str(t).lower() for t in payload.get("tags") or []}
    for trigger in sorted(config.TRIGGERS, key=lambda t: t.priority):
        if trigger.required_tags[0] in tags:
            return trigger.id
    return None


def ingest_inbound_lead(payload: dict[str, Any], *, ghl: GHLClient | None = None, store: Store | None = None) -> dict[str, Any]:
    """Create/update contact in Lindsey sub-account and enqueue for calling."""
    ghl = ghl or GHLClient()
    store = store or Store()

    phone = (payload.get("phone") or payload.get("phoneNumber") or "").strip()
    if not phone:
        return {"ok": False, "error": "phone is required"}

    trigger_id = resolve_trigger_id(payload)
    if not trigger_id:
        return {"ok": False, "error": "no matching trigger_id or trigger tag"}

    trigger = TRIGGER_BY_ID[trigger_id]
    tags = [str(t) for t in payload.get("tags") or []]
    if trigger.required_tags[0] not in {t.lower() for t in tags}:
        tags.append(trigger.required_tags[0])
    tags.append("ai-caller-inbound")
    if payload.get("source_contact_id"):
        tags.append(f"source-{payload['source_contact_id'][:20]}")

    tag_set = {t.lower() for t in tags}
    if has_exclusion_tag(tag_set):
        return {"ok": False, "error": "exclusion tag present — not queued"}

    contact = ghl.upsert_contact(
        phone=phone,
        first_name=payload.get("firstName", ""),
        last_name=payload.get("lastName", ""),
        email=payload.get("email", ""),
        tags=tags,
        timezone=payload.get("timezone", ""),
    )
    if not contact:
        return {"ok": False, "error": "failed to create contact in Lindsey sub-account"}

    contact_id = contact.get("id") or contact.get("contactId", "")
    campaign_id = resolve_campaign_from_tags(tag_set)
    source_note = payload.get("source", "inbound webhook")
    brief = (
        f"Warm follow-up — {trigger.name}\n"
        f"Campaign: {get_campaign(campaign_id).name}\n"
        f"Contact: {payload.get('firstName', '')} {payload.get('lastName', '')}\n"
        f"Phone: {phone}\n"
        f"Source: {source_note}"
    )

    queue_id = store.enqueue(
        contact_id=contact_id,
        trigger_id=trigger_id,
        phone=phone,
        first_name=payload.get("firstName", ""),
        last_name=payload.get("lastName", ""),
        email=payload.get("email", ""),
        timezone=payload.get("timezone", ""),
        tags=sorted(tag_set),
        brief=brief,
        campaign_id=campaign_id,
    )
    if not queue_id:
        return {"ok": True, "queued": False, "contact_id": contact_id, "reason": "already pending"}

    logger.info(
        "Inbound lead queued: contact=%s trigger=%s campaign=%s queue=%s",
        contact_id,
        trigger_id,
        campaign_id,
        queue_id,
    )
    return {
        "ok": True,
        "queued": True,
        "contact_id": contact_id,
        "queue_id": queue_id,
        "trigger_id": trigger_id,
        "campaign_id": campaign_id,
    }
