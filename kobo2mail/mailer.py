"""Build and send the email over Gmail or any SMTP server (standard library only)."""

import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

GMAIL_HOST = "smtp.gmail.com"
GMAIL_PORT = 465


class MailError(RuntimeError):
    pass


def build_message(*, sender, sender_name, to, subject, text, html, reply_to="", bcc="", attachments=()):
    """attachments: (filename, pdf_bytes) pairs."""
    msg = EmailMessage()
    msg["From"] = formataddr((sender_name, sender)) if sender_name else sender
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=sender.rsplit("@", 1)[-1] if "@" in sender else None)
    if reply_to:
        msg["Reply-To"] = reply_to
    if bcc:
        # smtplib.send_message delivers to Bcc recipients and strips the header.
        msg["Bcc"] = bcc
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    for filename, data in attachments:
        msg.add_attachment(data, maintype="application", subtype="pdf", filename=filename)
    return msg


def _require(env, name):
    value = env.get(name, "").strip()
    if not value:
        raise MailError(f"Missing required setting {name}")
    return value


def send(msg, provider, env=None):
    env = os.environ if env is None else env
    user = _require(env, "SMTP_USER")
    password = _require(env, "SMTP_PASSWORD")
    context = ssl.create_default_context()

    if provider == "gmail":
        host, port, use_ssl = GMAIL_HOST, GMAIL_PORT, True
    elif provider == "smtp":
        host = _require(env, "SMTP_HOST")
        port = int(env.get("SMTP_PORT", "").strip() or 587)
        use_ssl = port == 465
    else:
        raise MailError(f"Unknown provider {provider!r}")

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as server:
                server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as server:
                server.starttls(context=context)
                server.login(user, password)
                server.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        # Report the error class only: SMTP responses can echo recipient addresses.
        raise MailError(f"Sending failed via {host}:{port} ({type(exc).__name__})") from None
