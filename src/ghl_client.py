"""GoHighLevel API client."""

from __future__ import annotations

import logging
from typing import Any

import requests

from src import config

logger = logging.getLogger(__name__)


class GHLClient:
    def __init__(
        self,
        api_token: str | None = None,
        location_id: str | None = None,
    ) -> None:
        self.api_token = api_token or config.GHL_API_TOKEN
        self.location_id = location_id or config.GHL_LOCATION_ID
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_token}",
                "Version": "2021-07-28",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{config.GHL_BASE_URL}{path}"
        resp = self.session.request(method, url, timeout=30, **kwargs)
        if not resp.ok:
            logger.error("GHL %s %s failed (%s): %s", method, path, resp.status_code, resp.text[:500])
        resp.raise_for_status()
        if resp.text:
            return resp.json()
        return {}

    def get_contact(self, contact_id: str) -> dict[str, Any] | None:
        try:
            data = self._request("GET", f"/contacts/{contact_id}")
            return data.get("contact", data)
        except requests.RequestException as exc:
            logger.error("GHL get_contact failed for %s: %s", contact_id, exc)
            return None

    def search_contacts_by_tag(self, tag: str, limit: int = 100) -> list[dict[str, Any]]:
        """Search contacts carrying a tag. Tries filter search, then paginated list fallback."""
        contacts = self._search_by_tag_filter(tag, limit)
        if contacts:
            return contacts
        return self._list_contacts_filter_tag(tag, limit)

    def _search_by_tag_filter(self, tag: str, limit: int) -> list[dict[str, Any]]:
        filter_variants = [
            [{"field": "tags", "operator": "contains", "value": tag}],
            [{"field": "tags", "operator": "eq", "value": tag}],
            [{"field": "tags", "operator": "in", "value": [tag]}],
        ]
        for filters in filter_variants:
            try:
                data = self._request(
                    "POST",
                    "/contacts/search",
                    json={
                        "locationId": self.location_id,
                        "page": 1,
                        "pageLimit": limit,
                        "filters": filters,
                    },
                )
                contacts = data.get("contacts", [])
                if contacts:
                    return contacts
            except requests.RequestException:
                continue
        return []

    def _list_contacts_filter_tag(self, tag: str, limit: int) -> list[dict[str, Any]]:
        """Fallback: paginate GET /contacts and filter by tag client-side."""
        matched: list[dict[str, Any]] = []
        tag_lower = tag.lower()
        try:
            data = self._request(
                "GET",
                "/contacts/",
                params={"locationId": self.location_id, "limit": min(limit, 100)},
            )
            for contact in data.get("contacts", []):
                tags = {t.lower() for t in contact.get("tags", []) if isinstance(t, str)}
                if tag_lower in tags:
                    matched.append(contact)
                    if len(matched) >= limit:
                        break
        except requests.RequestException as exc:
            logger.error("GHL list contacts fallback failed for tag %s: %s", tag, exc)
        return matched

    def add_tags(self, contact_id: str, tags: list[str]) -> bool:
        if not tags:
            return True
        try:
            self._request(
                "POST",
                f"/contacts/{contact_id}/tags",
                json={"tags": tags},
            )
            return True
        except requests.RequestException as exc:
            logger.error("GHL add_tags failed for %s: %s", contact_id, exc)
            return False

    def add_note(self, contact_id: str, body: str, title: str = "AI Warm Follow-Up") -> bool:
        try:
            self._request(
                "POST",
                f"/contacts/{contact_id}/notes",
                json={"body": body, "title": title},
            )
            return True
        except requests.RequestException as exc:
            logger.error("GHL add_note failed for %s: %s", contact_id, exc)
            return False

    def add_to_workflow(self, contact_id: str, workflow_id: str) -> bool:
        if not workflow_id:
            return False
        try:
            self._request(
                "POST",
                f"/contacts/{contact_id}/workflow/{workflow_id}",
                json={},
            )
            return True
        except requests.RequestException as exc:
            logger.error("GHL add_to_workflow failed for %s: %s", contact_id, exc)
            return False

    @staticmethod
    def contact_tags(contact: dict[str, Any]) -> set[str]:
        raw = contact.get("tags") or []
        return {t.lower().strip() for t in raw if isinstance(t, str)}

    @staticmethod
    def is_dnd(contact: dict[str, Any]) -> bool:
        if contact.get("dnd"):
            return True
        dnd_settings = contact.get("dndSettings") or {}
        return bool(dnd_settings.get("Call") or dnd_settings.get("call"))

    @staticmethod
    def contact_phone(contact: dict[str, Any]) -> str:
        return (contact.get("phone") or contact.get("phoneNumber") or "").strip()

    @staticmethod
    def contact_timezone(contact: dict[str, Any]) -> str:
        return (
            contact.get("timezone")
            or contact.get("timeZone")
            or contact.get("country")
            or ""
        ).strip()

    @staticmethod
    def build_brief(contact: dict[str, Any], trigger_name: str) -> str:
        name = f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip()
        tags = ", ".join(sorted(GHLClient.contact_tags(contact)))
        return (
            f"Warm follow-up call — {trigger_name}\n"
            f"Contact: {name or 'Unknown'}\n"
            f"Email: {contact.get('email', 'n/a')}\n"
            f"Tags: {tags or 'none'}\n"
            f"Source: GHL trigger monitor"
        )
