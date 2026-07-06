import json

from config import ENABLE_REPLY_POLLING, ENABLE_SCRAPER, MOCK_REPLY
from ml_utils.validators.experience import is_free_email
from mailer.send_verification import send_verification_email


def _dedup(flags: list[str]) -> list[str]:
    return list(dict.fromkeys(flags))


def _poll_reply(hr_email: str, flags: list[str], demo_mode: bool) -> dict:
    """Optional IMAP round-trip; only used when ENABLE_REPLY_POLLING is set."""
    from mailer.check_reply import check_reply_status

    reply = check_reply_status(hr_email)
    if reply == "confirmed":
        return {"verification_status": "System Verified", "flags": _dedup(flags), "demo_mode": demo_mode}
    if reply == "denied":
        flags.append("REPLY_DENIED")
        return {"verification_status": "Red Flagged", "flags": _dedup(flags), "demo_mode": demo_mode}
    flags.append("NO_REPLY")
    return {"verification_status": "Pending Verification", "flags": _dedup(flags), "demo_mode": demo_mode}


def verify_experience(doc) -> dict:
    fields = json.loads(doc.extracted_fields or "{}")
    flags = json.loads(doc.flags or "[]")
    hr_email = fields.get("hr_email")
    company = fields.get("company_name")
    demo_mode = False

    if MOCK_REPLY in ("confirmed", "denied", "no_reply"):
        status_map = {
            "confirmed": "System Verified",
            "denied": "Red Flagged",
            "no_reply": "Pending Verification",
        }
        if MOCK_REPLY == "denied":
            flags.append("REPLY_DENIED")
        if MOCK_REPLY == "no_reply":
            flags.append("NO_REPLY")
        return {"verification_status": status_map[MOCK_REPLY], "flags": _dedup(flags), "demo_mode": True}

    target_email = hr_email
    if not target_email and company and ENABLE_SCRAPER:
        from scrapers.company_scraper import find_company_email

        target_email = find_company_email(company)

    if not target_email:
        flags.append("NO_EMAIL" if company else "NO_COMPANY")
        return {"verification_status": "Red Flagged", "flags": _dedup(flags), "demo_mode": demo_mode}

    if is_free_email(target_email):
        flags.append("FREE_EMAIL")
        return {"verification_status": "Red Flagged", "flags": _dedup(flags), "demo_mode": demo_mode}

    sent, demo_mode = send_verification_email(
        target_email,
        fields.get("employee_name", "the applicant"),
        company or "your organization",
    )
    if demo_mode:
        flags.append("DEMO_MODE_EMAIL")
    if not sent:
        flags.append("EMAIL_BOUNCED")
        return {"verification_status": "Manual Review Required", "flags": _dedup(flags), "demo_mode": demo_mode}

    # Send-only (production default): the request was emailed; a human resolves it.
    if ENABLE_REPLY_POLLING:
        return _poll_reply(target_email, flags, demo_mode)

    flags.append("EMAIL_SENT")
    return {"verification_status": "Pending Verification", "flags": _dedup(flags), "demo_mode": demo_mode}
