"""
Email notifier. All credentials come from environment variables so nothing
sensitive is committed. See .env.example.

Required env vars:
    SMTP_HOST       e.g. smtp.gmail.com
    SMTP_PORT       e.g. 587
    SMTP_USER       your SMTP username / email
    SMTP_PASS       app password (NOT your normal password for Gmail)
    EMAIL_FROM      from address (defaults to SMTP_USER)
    EMAIL_TO        comma-separated recipient list

If SMTP is not configured, send_email() prints to stdout instead so the scanner
still works during testing.
"""

import os
import smtplib
import ssl
from email.message import EmailMessage


def _cfg():
    return {
        "host": os.environ.get("SMTP_HOST"),
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": os.environ.get("SMTP_USER"),
        "password": os.environ.get("SMTP_PASS"),
        "from": os.environ.get("EMAIL_FROM") or os.environ.get("SMTP_USER"),
        "to": [a.strip() for a in os.environ.get("EMAIL_TO", "").split(",") if a.strip()],
    }


def render_html(title, rows, columns):
    """Build a simple HTML table email body."""
    if not rows:
        return f"<h3>{title}</h3><p>No matches this scan.</p>"
    head = "".join(f"<th style='text-align:left;padding:6px 10px'>{c}</th>" for c, _ in columns)
    body = ""
    for r in rows:
        cells = "".join(
            f"<td style='padding:6px 10px;border-top:1px solid #eee'>{r.get(key, '')}</td>"
            for _, key in columns
        )
        body += f"<tr>{cells}</tr>"
    return (
        f"<h3>{title}</h3>"
        f"<table style='border-collapse:collapse;font-family:sans-serif;font-size:14px'>"
        f"<thead style='background:#0b132b;color:#fff'><tr>{head}</tr></thead>"
        f"<tbody>{body}</tbody></table>"
    )


def send_email(subject, html_body):
    c = _cfg()
    if not (c["host"] and c["user"] and c["password"] and c["to"]):
        print("[notify] SMTP not configured — printing instead:\n")
        print(subject)
        print(html_body)
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = c["from"]
    msg["To"] = ", ".join(c["to"])
    msg.set_content("This report is best viewed as HTML.")
    msg.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()
    with smtplib.SMTP(c["host"], c["port"]) as server:
        server.starttls(context=context)
        server.login(c["user"], c["password"])
        server.send_message(msg)
    print(f"[notify] emailed {len(c['to'])} recipient(s)")
    return True
