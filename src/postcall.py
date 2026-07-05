"""Post-call processing: GHL notes, tags, nurture workflow."""

from __future__ import annotations

import logging
from typing import Any

from src import config
from src.ghl_client import GHLClient
from src.store import Store

logger = logging.getLogger(__name__)


def classify_outcome(report: dict[str, Any]) -> str:
    analysis = report.get("analysis") or {}
    structured = analysis.get("structuredData") or {}
    outcome = structured.get("outcome")
    if structured.get("dnc_requested"):
        return "dnc_requested"
    if outcome in config.OUTCOME_TAGS:
        return outcome
    summary = (analysis.get("summary") or "").lower()
    if "book" in summary and "consult" in summary:
        return "booked"
    if "not ready" in summary or "call back later" in summary:
        return "not_ready"
    if "do not call" in summary or "remove me" in summary:
        return "dnc_requested"
    return "other"


def format_call_note(
    *,
    outcome: str,
    transcript: str,
    summary: str = "",
    recording_url: str = "",
    cost: float | None = None,
) -> str:
    lines = [
        "🤖 AI Warm Follow-Up Call",
        f"Outcome: {outcome}",
    ]
    if summary:
        lines.append(f"Summary: {summary}")
    if cost is not None:
        lines.append(f"Cost: ${cost:.2f}")
    if recording_url:
        lines.append(f"Recording: {recording_url}")
    if transcript:
        lines.append("")
        lines.append("Transcript:")
        lines.append(transcript[:4000])
    return "\n".join(lines)


class PostCallProcessor:
    def __init__(
        self,
        ghl: GHLClient | None = None,
        store: Store | None = None,
    ) -> None:
        self.ghl = ghl or GHLClient()
        self.store = store or Store()

    def process(
        self,
        *,
        contact_id: str,
        report: dict[str, Any],
        queue_id: int | None = None,
    ) -> str:
        outcome = classify_outcome(report)
        transcript = _extract_transcript(report)
        summary = (report.get("analysis") or {}).get("summary", "")
        recording_url = report.get("recordingUrl") or report.get("recording", {}).get("url", "")
        cost = _extract_cost(report)
        duration = _extract_duration(report)
        call_id = report.get("id") or report.get("callId", "")

        self.store.record_attempt(
            contact_id=contact_id,
            queue_id=queue_id,
            vapi_call_id=call_id,
            outcome=outcome,
            cost=cost,
            duration_seconds=duration,
            recording_url=recording_url,
            transcript=transcript,
        )

        note = format_call_note(
            outcome=outcome,
            transcript=transcript,
            summary=summary,
            recording_url=recording_url,
            cost=cost,
        )
        self.ghl.add_note(contact_id, note)

        tag = config.OUTCOME_TAGS.get(outcome)
        if tag:
            self.ghl.add_tags(contact_id, [tag])

        if outcome == "not_ready" and config.GHL_NURTURE_WORKFLOW_ID:
            self.ghl.add_to_workflow(contact_id, config.GHL_NURTURE_WORKFLOW_ID)

        if outcome == "dnc_requested":
            self.ghl.add_tags(contact_id, [config.OUTCOME_TAGS["dnc_requested"]])

        if queue_id:
            status = "completed" if outcome != "no_answer" else "pending"
            self.store.mark_queue_status(queue_id, status)

        if call_id:
            self.store.clear_active_call(call_id)

        return outcome


def _extract_transcript(report: dict[str, Any]) -> str:
    artifact = report.get("artifact") or {}
    messages = artifact.get("messages") or report.get("messages") or []
    lines: list[str] = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("message") or msg.get("content") or ""
        if content:
            lines.append(f"{role}: {content}")
    if lines:
        return "\n".join(lines)
    return report.get("transcript", "")


def _extract_cost(report: dict[str, Any]) -> float | None:
    cost = report.get("cost")
    if cost is not None:
        return float(cost)
    costs = report.get("costs") or []
    if costs:
        return float(sum(c.get("cost", 0) for c in costs))
    return None


def _extract_duration(report: dict[str, Any]) -> int | None:
    duration = report.get("durationSeconds") or report.get("duration")
    if duration is not None:
        return int(duration)
    started = report.get("startedAt")
    ended = report.get("endedAt")
    if started and ended:
        from datetime import datetime

        try:
            s = datetime.fromisoformat(started.replace("Z", "+00:00"))
            e = datetime.fromisoformat(ended.replace("Z", "+00:00"))
            return int((e - s).total_seconds())
        except ValueError:
            pass
    return None
