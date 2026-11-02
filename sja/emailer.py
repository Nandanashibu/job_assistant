"""Send emails, or save them as .eml files in data/outbox when EMAIL_DRY_RUN is on.

Dry run is the default so you can test everything without emailing real HR inboxes.
To really send: create a Gmail App Password (Google Account -> Security -> 2-Step
Verification -> App passwords) and put it in the .env file (see .env.example).
"""
import mimetypes
import re
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import config
from sja import database as db


def build_message(to_addr, subject, body, attachment=None, reply_to=None):
    msg = EmailMessage()
    msg["From"] = config.SMTP_USER or "smart-job-assistant@localhost"
    msg["To"] = to_addr
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body)
    if attachment and Path(attachment).exists():
        ctype, _ = mimetypes.guess_type(str(attachment))
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        msg.add_attachment(Path(attachment).read_bytes(), maintype=maintype, subtype=subtype,
                           filename=Path(attachment).name)
    return msg


def send_email(user_id, to_addr, subject, body, attachment=None, reply_to=None):
    """Return 'saved' (dry run), 'sent' or 'failed: <reason>'."""
    msg = build_message(to_addr, subject, body, attachment, reply_to)
    if config.EMAIL_DRY_RUN or not (config.SMTP_USER and config.SMTP_APP_PASSWORD):
        safe = re.sub(r"[^\w-]+", "_", subject)[:60]
        path = config.OUTBOX_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{safe}.eml"
        path.write_bytes(bytes(msg))
        status = "saved"
    else:
        try:
            with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=ssl.create_default_context()) as smtp:
                smtp.login(config.SMTP_USER, config.SMTP_APP_PASSWORD)
                smtp.send_message(msg)
            status = "sent"
        except Exception as exc:
            status = f"failed: {exc}"
    db.log_email(user_id, to_addr, subject, body, str(attachment or ""), status)
    return status
