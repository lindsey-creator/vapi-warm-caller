"""Main orchestration loop: poll triggers, run compliance, dial via Vapi."""

from __future__ import annotations

import argparse
import logging
import time

from src import config
from src.compliance import evaluate_contact
from src.store import Store
from src.triggers import TriggerMonitor
from src.vapi_client import VapiClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.monitor = TriggerMonitor()
        self.store = Store()
        self.vapi = VapiClient()

    def run_once(self) -> None:
        self.monitor.poll()
        pending = self.store.get_pending_queue()
        active = self.store.count_active_calls()
        slots = max(0, config.MAX_CONCURRENT_CALLS - active)

        if slots == 0:
            logger.info("At concurrent call cap (%s active)", active)
            return

        for item in pending[:slots]:
            contact = self.monitor.contact_from_queue_item(item)
            gate = evaluate_contact(contact, self.store)
            if not gate.allowed:
                logger.info(
                    "Skipping queue %s (contact %s): %s",
                    item["id"],
                    item["contact_id"],
                    gate.reason,
                )
                if "outside" in gate.reason or "min" in gate.reason:
                    continue
                self.store.mark_queue_status(item["id"], "blocked")
                continue

            if self.dry_run:
                logger.info(
                    "[dry-run] Would dial contact %s (%s)",
                    item["contact_id"],
                    item["phone"],
                )
                continue

            try:
                call = self.vapi.create_call(
                    phone=item["phone"],
                    contact_id=item["contact_id"],
                    first_name=item.get("first_name") or "",
                    brief=item.get("brief") or "",
                    queue_id=item["id"],
                )
            except Exception as exc:
                logger.error("Vapi dial failed for queue %s: %s", item["id"], exc)
                continue

            call_id = call.get("id") or call.get("callId", "")
            self.store.register_active_call(call_id, item["contact_id"], item["id"])
            self.store.mark_queue_status(item["id"], "dialing")
            logger.info("Dialing contact %s — Vapi call %s", item["contact_id"], call_id)

    def run_continuous(self) -> None:
        logger.info(
            "Orchestrator started (poll every %ss, max %s concurrent)",
            config.POLL_INTERVAL_SECONDS,
            config.MAX_CONCURRENT_CALLS,
        )
        while True:
            try:
                self.run_once()
            except Exception:
                logger.exception("Orchestrator cycle failed")
            time.sleep(config.POLL_INTERVAL_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Warm follow-up call orchestrator")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single poll/dial cycle instead of looping",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Poll and run compliance but do not dial",
    )
    args = parser.parse_args()
    orch = Orchestrator(dry_run=args.dry_run)
    if args.once:
        orch.run_once()
    else:
        orch.run_continuous()


if __name__ == "__main__":
    main()
