"""Webhook server: Vapi events, live booking, dashboard API."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

from src import config
from src.gcal_client import GCalClient, parse_booking_tool_args
from src.ghl_client import GHLClient
from src.postcall import PostCallProcessor
from src.store import Store

logger = logging.getLogger(__name__)

app = Flask(__name__)

DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"

_store: Store | None = None
_ghl: GHLClient | None = None
_postcall: PostCallProcessor | None = None
_gcal: GCalClient | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


def get_ghl() -> GHLClient:
    global _ghl
    if _ghl is None:
        _ghl = GHLClient()
    return _ghl


def get_postcall() -> PostCallProcessor:
    global _postcall
    if _postcall is None:
        _postcall = PostCallProcessor(ghl=get_ghl(), store=get_store())
    return _postcall


def get_gcal() -> GCalClient:
    global _gcal
    if _gcal is None:
        _gcal = GCalClient()
    return _gcal


def _verify_webhook() -> bool:
    if not config.VAPI_WEBHOOK_SECRET:
        return True
    secret = request.headers.get("X-Vapi-Secret") or request.headers.get("x-vapi-secret")
    return secret == config.VAPI_WEBHOOK_SECRET


def _contact_id_from_call(call: dict[str, Any]) -> str | None:
    metadata = call.get("metadata") or {}
    if metadata.get("contactId"):
        return str(metadata["contactId"])
    overrides = call.get("assistantOverrides") or {}
    vars_ = overrides.get("variableValues") or {}
    if vars_.get("contactId"):
        return str(vars_["contactId"])
    customer = call.get("customer") or {}
    cust_meta = customer.get("metadata") or {}
    return cust_meta.get("contactId")


def _queue_id_from_call(call: dict[str, Any]) -> int | None:
    metadata = call.get("metadata") or {}
    raw = metadata.get("queueId")
    if raw is None:
        overrides = call.get("assistantOverrides") or {}
        raw = (overrides.get("variableValues") or {}).get("queueId")
    try:
        return int(raw) if raw else None
    except (TypeError, ValueError):
        return None


@app.route("/")
def dashboard() -> Any:
    return send_from_directory(DASHBOARD_DIR, "index.html")


@app.route("/health")
def health() -> Any:
    return jsonify({"status": "ok"})


@app.route("/api/dashboard")
def dashboard_api() -> Any:
    return jsonify(get_store().get_dashboard_stats())


@app.route("/vapi/webhook", methods=["POST"])
def vapi_webhook() -> Any:
    if not _verify_webhook():
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    message = payload.get("message") or payload
    msg_type = message.get("type")

    logger.info("Vapi webhook: %s", msg_type)

    if msg_type == "tool-calls":
        return _handle_tool_calls(message)

    if msg_type == "end-of-call-report":
        return _handle_end_of_call(message)

    if msg_type == "status-update":
        return _handle_status_update(message)

    return jsonify({"ok": True})


def _handle_tool_calls(message: dict[str, Any]) -> Any:
    tool_calls = message.get("toolCallList") or []
    call = message.get("call") or {}
    contact_id = _contact_id_from_call(call) or ""
    results = []

    for tc in tool_calls:
        name = tc.get("name")
        tc_id = tc.get("id")
        args = tc.get("arguments") or tc.get("parameters") or {}

        if name == "book_appointment":
            result = _book_appointment(contact_id, call.get("id"), args)
        else:
            result = f"Unknown tool: {name}"

        results.append({"toolCallId": tc_id, "result": result})

    return jsonify({"results": results})


def _book_appointment(contact_id: str, vapi_call_id: str | None, args: dict[str, Any]) -> str:
    parsed = parse_booking_tool_args(args)
    if not parsed["preferred_date"] or not parsed["preferred_time"]:
        return "Need a preferred date and time to book."

    try:
        gcal = get_gcal()
    except Exception as exc:
        logger.error("GCal init failed: %s", exc)
        return "Calendar unavailable — Lindsey's team will follow up manually."

    slot = gcal.find_free_slot(
        parsed["preferred_date"],
        parsed["preferred_time"],
        parsed["timezone"],
    )
    if not slot:
        return "No open slots near that time. Ask for another day or time."

    ghl = get_ghl()
    contact = ghl.get_contact(contact_id) if contact_id else {}
    name = f"{(contact or {}).get('firstName', '')} {(contact or {}).get('lastName', '')}".strip()
    email = (contact or {}).get("email", "")

    brief = parsed["notes"]
    if contact:
        brief = brief or ghl.build_brief(contact, "Booked on call")

    try:
        event = gcal.book_event(
            contact_name=name or "Lead",
            contact_email=email,
            slot_start=slot[0],
            slot_end=slot[1],
            brief=brief,
            timezone=parsed["timezone"],
        )
    except Exception as exc:
        logger.error("GCal book failed: %s", exc)
        return "Could not book that slot — try another time."

    if contact_id:
        get_store().record_booking(
            contact_id=contact_id,
            vapi_call_id=vapi_call_id,
            slot_start=slot[0],
            slot_end=slot[1],
            gcal_event_id=event.get("id"),
        )
        ghl.add_tags(contact_id, [config.OUTCOME_TAGS["booked"]])

    return f"Booked for {slot[0]} to {slot[1]}. Calendar invite sent."


def _handle_end_of_call(message: dict[str, Any]) -> Any:
    report = message.get("call") or message
    contact_id = _contact_id_from_call(report)
    queue_id = _queue_id_from_call(report)

    if contact_id:
        outcome = get_postcall().process(
            contact_id=contact_id,
            report=report,
            queue_id=queue_id,
        )
        logger.info("Post-call processed for %s: %s", contact_id, outcome)

    return jsonify({"ok": True})


def _handle_status_update(message: dict[str, Any]) -> Any:
    call = message.get("call") or {}
    status = (call.get("status") or "").lower()
    call_id = call.get("id")
    if call_id and status in {"ended", "completed", "failed", "busy", "no-answer"}:
        get_store().clear_active_call(call_id)
    return jsonify({"ok": True})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host="0.0.0.0", port=8080, debug=True)
