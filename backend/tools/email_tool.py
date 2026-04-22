"""Email sending utility for HTML briefings."""
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import unescape
from typing import List

from backend.config import (
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_TIMEOUT,
    SMTP_USE_SSL,
    SMTP_USE_TLS,
    SMTP_USER,
)


EMAIL_RE = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
MAX_BODY_CHARS = 180_000


def _normalize_recipients(to_address: str) -> List[str]:
    raw_parts = [p.strip() for p in (to_address or "").replace(";", ",").split(",")]
    recipients = [p for p in raw_parts if p]
    # Keep unique order
    deduped: List[str] = []
    seen = set()
    for rec in recipients:
        lower = rec.lower()
        if lower in seen:
            continue
        seen.add(lower)
        deduped.append(rec)
    return deduped


def _invalid_recipients(recipients: List[str]) -> List[str]:
    return [r for r in recipients if not EMAIL_RE.match(r)]


def _html_to_text(html_body: str) -> str:
    text = TAG_RE.sub(" ", html_body or "")
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:10_000]


def send_email(to_address: str, subject: str, html_body: str) -> dict:
    """
    Send an HTML email via SMTP.
    Returns {"success": bool, "message": str}.
    """
    recipients = _normalize_recipients(to_address)
    if not recipients:
        return {
            "success": False,
            "message": "No recipient email provided.",
        }

    invalid = _invalid_recipients(recipients)
    if invalid:
        return {
            "success": False,
            "message": f"Invalid recipient email: {', '.join(invalid)}",
        }

    if not SMTP_HOST or not SMTP_PORT:
        return {
            "success": False,
            "message": "SMTP host/port not configured.",
        }

    if not SMTP_USER or not SMTP_PASSWORD:
        return {
            "success": False,
            "message": "SMTP not configured. Set SMTP_USER and SMTP_PASSWORD in .env.",
        }

    safe_html = (html_body or "")[:MAX_BODY_CHARS]

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SMTP_FROM or SMTP_USER
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject.strip()[:180]

        text_body = _html_to_text(safe_html)
        if text_body:
            msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(safe_html, "html", "utf-8"))

        if SMTP_USE_SSL:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT)

        with server:
            server.ehlo()
            if SMTP_USE_TLS and not SMTP_USE_SSL:
                server.starttls()
                server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM or SMTP_USER, recipients, msg.as_string())

        return {
            "success": True,
            "message": f"Briefing delivered to {', '.join(recipients)}",
        }

    except smtplib.SMTPAuthenticationError:
        return {
            "success": False,
            "message": "SMTP authentication failed. Check SMTP_USER and SMTP_PASSWORD (app password).",
        }
    except smtplib.SMTPRecipientsRefused:
        return {
            "success": False,
            "message": "SMTP rejected recipient address. Verify destination email.",
        }
    except smtplib.SMTPServerDisconnected:
        return {
            "success": False,
            "message": "SMTP server disconnected. Check SMTP_HOST/SMTP_PORT/TLS settings.",
        }
    except TimeoutError:
        return {
            "success": False,
            "message": "SMTP connection timed out. Check network or SMTP host.",
        }
    except Exception as exc:
        return {
            "success": False,
            "message": f"Email delivery failed: {str(exc)}",
        }
