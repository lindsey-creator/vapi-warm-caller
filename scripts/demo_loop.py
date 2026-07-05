#!/usr/bin/env python3
"""
End-to-end demo without live Vapi/GHL/GCal credentials.
Simulates: trigger poll → queue → compliance → mock dial → webhook post-call.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.compliance import evaluate_contact
from src.postcall import PostCallProcessor
from src.store import Store
from src.triggers import TriggerMonitor


def main() -> None:
    store = Store()
    monitor = TriggerMonitor(store=store)

    # Mock GHL
    mock_contact = {
        "id": "demo-contact-001",
        "firstName": "Lindsey",
        "lastName": "Test",
        "phone": "+15555550100",
        "email": "lindsey.test@example.com",
        "tags": ["form-fill"],
        "timezone": "America/New_York",
    }

    class MockGHL:
        def search_contacts_by_tag(self, tag, limit=100):
            return [mock_contact] if tag == "form-fill" else []

        contact_tags = staticmethod(lambda c: {t.lower() for t in c.get("tags", [])})
        contact_phone = staticmethod(lambda c: c.get("phone", ""))
        contact_timezone = staticmethod(lambda c: c.get("timezone", ""))
        build_brief = staticmethod(lambda c, n: f"Demo brief for {n}")

        def get_contact(self, contact_id):
            return mock_contact if contact_id == mock_contact["id"] else None

        def add_note(self, contact_id, body):
            print(f"\n--- GHL NOTE ({contact_id}) ---\n{body}\n")
            return True

        def add_tags(self, contact_id, tags):
            print(f"GHL tags applied to {contact_id}: {tags}")
            return True

        def add_to_workflow(self, contact_id, workflow_id):
            print(f"GHL workflow {workflow_id} triggered for {contact_id}")
            return True

    monitor.ghl = MockGHL()
    queued = monitor.poll()
    print(f"Queued {len(queued)} contact(s)")

    pending = store.get_pending_queue()
    item = pending[0]
    contact = monitor.contact_from_queue_item(item)
    gate = evaluate_contact(
        contact,
        store,
        now=datetime(2026, 7, 5, 18, 0, tzinfo=timezone.utc),
    )
    print(f"Compliance gate: {'PASS' if gate.allowed else 'BLOCK'} — {gate.reason or 'ok'}")

    # Simulate Vapi end-of-call webhook payload
    report = {
        "id": "demo-call-001",
        "metadata": {"contactId": item["contact_id"], "queueId": item["id"]},
        "analysis": {
            "summary": "Lead booked a consultation for next Tuesday.",
            "structuredData": {"outcome": "booked"},
        },
        "cost": 0.38,
        "durationSeconds": 142,
        "recordingUrl": "https://example.com/recording/demo",
        "artifact": {
            "messages": [
                {"role": "assistant", "message": "Hey, is this Lindsey?"},
                {"role": "user", "message": "Yeah, what's up?"},
                {"role": "assistant", "message": "You checked us out online — got a minute?"},
            ]
        },
    }

    processor = PostCallProcessor(ghl=MockGHL(), store=store)
    outcome = processor.process(
        contact_id=item["contact_id"],
        report=report,
        queue_id=item["id"],
    )
    print(f"Post-call outcome: {outcome}")
    print("\nDashboard stats:", json.dumps(store.get_dashboard_stats(), indent=2))


if __name__ == "__main__":
    main()
