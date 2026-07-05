"""Poll GHL for trigger conditions and enqueue eligible contacts."""

from __future__ import annotations

import logging
from typing import Any

from src import config
from src.compliance import has_exclusion_tag, match_trigger
from src.ghl_client import GHLClient
from src.store import Store

logger = logging.getLogger(__name__)


class TriggerMonitor:
    def __init__(
        self,
        ghl: GHLClient | None = None,
        store: Store | None = None,
    ) -> None:
        self.ghl = ghl or GHLClient()
        self.store = store or Store()

    def poll(self) -> list[int]:
        """Scan all triggers and enqueue new contacts. Returns new queue IDs."""
        queued: list[int] = []
        seen_contacts: set[str] = set()

        for trigger in sorted(config.TRIGGERS, key=lambda t: t.priority):
            contacts = self.ghl.search_contacts_by_tag(trigger.required_tags[0])
            for contact in contacts:
                contact_id = contact.get("id") or contact.get("contactId")
                if not contact_id or contact_id in seen_contacts:
                    continue

                tags = self.ghl.contact_tags(contact)
                if not match_trigger(tags, trigger.required_tags):
                    continue
                if has_exclusion_tag(tags):
                    continue

                phone = self.ghl.contact_phone(contact)
                if not phone:
                    continue

                brief = self.ghl.build_brief(contact, trigger.name)
                queue_id = self.store.enqueue(
                    contact_id=contact_id,
                    trigger_id=trigger.id,
                    phone=phone,
                    first_name=contact.get("firstName", ""),
                    last_name=contact.get("lastName", ""),
                    email=contact.get("email", ""),
                    timezone=self.ghl.contact_timezone(contact),
                    tags=sorted(tags),
                    brief=brief,
                )
                if queue_id:
                    seen_contacts.add(contact_id)
                    queued.append(queue_id)
                    logger.info(
                        "Queued contact %s for trigger %s (queue_id=%s)",
                        contact_id,
                        trigger.id,
                        queue_id,
                    )
        return queued

    def contact_from_queue_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        return self.ghl.get_contact(item["contact_id"])
