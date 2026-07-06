import smtplib
from email.mime.text import MIMEText

from config import SMTP_HOST, SMTP_PASS, SMTP_PORT, SMTP_USER


def send_verification_email(to_email: str, employee_name: str, company_name: str) -> tuple[bool, bool]:
    """Returns (success, demo_mode)."""
    if not SMTP_HOST or not SMTP_USER:
        return True, True

    body = (
        f"Dear {company_name} Team,\n\n"
        f"We are verifying employment documentation submitted by {employee_name}. "
        f"Please confirm whether this individual was employed with your organization "
        f"as stated in the experience letter on file.\n\n"
        f"Reply YES to confirm or NO to deny.\n\n"
        f"— DocVerify AI (automated verification)"
    )
    msg = MIMEText(body)
    msg["Subject"] = f"Employment verification request — {employee_name}"
    msg["From"] = SMTP_USER
    msg["To"] = to_email

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True, False
    except Exception:
        return False, False
