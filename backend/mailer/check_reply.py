import imaplib
import email
from email.header import decode_header

from config import IMAP_HOST, IMAP_PASS, IMAP_USER, MOCK_REPLY


def check_reply_status(expected_from: str | None = None) -> str:
    if MOCK_REPLY in ("confirmed", "denied", "no_reply"):
        if MOCK_REPLY == "confirmed":
            return "confirmed"
        if MOCK_REPLY == "denied":
            return "denied"
        return "no_reply"

    if not IMAP_HOST or not IMAP_USER:
        return "no_reply"

    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST)
        mail.login(IMAP_USER, IMAP_PASS)
        mail.select("inbox")
        _, messages = mail.search(None, "UNSEEN")
        ids = messages[0].split()
        for num in reversed(ids[-10:]):
            _, data = mail.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            subject = _decode(msg.get("Subject", ""))
            body = _get_body(msg).lower()
            if "yes" in body or "confirm" in subject.lower():
                mail.logout()
                return "confirmed"
            if "no" in body or "deny" in subject.lower() or "not employed" in body:
                mail.logout()
                return "denied"
        mail.logout()
    except Exception:
        pass
    return "no_reply"


def _decode(value: str) -> str:
    parts = decode_header(value)
    out = []
    for part, enc in parts:
        if isinstance(part, bytes):
            out.append(part.decode(enc or "utf-8", errors="ignore"))
        else:
            out.append(part)
    return "".join(out)


def _get_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(errors="ignore")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode(errors="ignore")
    return ""
