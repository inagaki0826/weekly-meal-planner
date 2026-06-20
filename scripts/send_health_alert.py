#!/usr/bin/env python3
"""
GitHub Actions entry point for the MHLW health alert system.
Runs daily at 22:00 UTC (07:00 JST).

Required environment variables:
  GEMINI_API_KEY      - Google Gemini API key
  GMAIL_USER          - Gmail address for sending
  GMAIL_APP_PASSWORD  - Gmail App Password (16 chars)
  ALERT_TO_EMAIL      - Recipient email address
"""
import os
import sys
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.health_alert import (
    load_seen_urls,
    save_seen_urls,
    process_new_articles,
    append_to_history,
    build_email_html,
)

JST = timezone(timedelta(hours=9))


def send_email(subject: str, html_body: str) -> None:
    gmail_user = os.environ["GMAIL_USER"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ["ALERT_TO_EMAIL"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(gmail_user, gmail_password)
        smtp.send_message(msg)


def main() -> None:
    run_date = datetime.now(JST).strftime("%Y-%m-%d")

    seen = load_seen_urls()
    articles, updated_seen = process_new_articles(seen)
    save_seen_urls(updated_seen)

    if not articles:
        print("新着記事なし。メール送信をスキップ。")
        return

    append_to_history(articles, run_date)
    subject, html_body = build_email_html(articles, run_date)
    send_email(subject, html_body)
    print(f"送信完了: {len(articles)}件")


if __name__ == "__main__":
    main()
