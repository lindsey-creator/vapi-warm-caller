"""8 PM daily summary email."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src import config
from src.store import Store

logger = logging.getLogger(__name__)


def build_summary_body(stats: dict) -> str:
    lines = [
        f"AI Caller Daily Summary — {stats['day']}",
        "",
        f"Total calls:     {stats['total_calls']}",
        f"Booked:          {stats['booked']}",
        f"Needs human:     {stats['needs_human']}",
        f"Vapi spend:      ${stats['spend']:.2f}",
        "",
        "Outcomes:",
    ]
    for outcome, count in sorted(stats.get("by_outcome", {}).items()):
        lines.append(f"  {outcome or 'unknown'}: {count}")
    return "\n".join(lines)


def send_daily_summary(store: Store | None = None) -> None:
    store = store or Store()
    stats = store.get_daily_summary_stats()
    body = build_summary_body(stats)

    if not config.SUMMARY_EMAIL_TO or not config.SMTP_USER:
        logger.warning("Email not configured — printing summary:\n%s", body)
        print(body)
        return

    msg = MIMEMultipart()
    msg["From"] = config.SMTP_USER
    msg["To"] = config.SUMMARY_EMAIL_TO
    msg["Subject"] = f"AI Caller Summary — {stats['day']}"
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
        server.starttls()
        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.send_message(msg)

    logger.info("Daily summary sent to %s", config.SUMMARY_EMAIL_TO)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    send_daily_summary()


if __name__ == "__main__":
    main()
