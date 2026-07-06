"""Experience letter field extraction and validation — pure OCR-based."""

from __future__ import annotations

import re
from config import FREE_EMAIL_DOMAINS
from ml_utils.ocr import OcrResult, get_full_text, get_average_confidence
from ml_utils.extract import find_value_near_label, get_text_in_region

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+91[\s\-]?)?[6-9]\d{9}")
DATE_RE = re.compile(
    r"\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|"
    r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}",
    re.I,
)
COMPANY_RE = re.compile(
    r"([A-Z][A-Za-z0-9\s&.,'\-]+(?:Pvt\.?\s*Ltd\.?|Limited|LLP|Inc\.?|Corporation|Technologies|Solutions|Services|Consulting|Enterprises|Group|Company))",
    re.I,
)
EXP_KEYWORDS = ["experience", "certify", "employed", "worked", "tenure", "designation",
                 "employment", "relieving", "service", "joining"]
PREFERRED_EMAIL_PREFIXES = ("hr@", "careers@", "jobs@", "recruitment@", "talent@", "admin@")

NAME_LABELS = ["name", "employee", "mr.", "ms.", "mrs."]
DESIGNATION_LABELS = ["designation", "position", "role", "title", "पदनाम"]
DEPARTMENT_LABELS = ["department", "dept", "division", "विभाग"]
JOINING_LABELS = ["joining", "join date", "date of joining", "from", "start"]
EXIT_LABELS = ["relieving", "exit", "last working", "to", "end date", "separation"]
SALARY_LABELS = ["salary", "ctc", "compensation", "remuneration", "package"]


def _rank_email(emails: list[str], company_name: str | None) -> str | None:
    """Pick the most relevant email (HR > corporate > personal)."""
    if not emails:
        return None

    def score(email: str) -> int:
        lower = email.lower()
        s = 0
        if any(lower.startswith(p) for p in PREFERRED_EMAIL_PREFIXES):
            s += 10
        if company_name:
            company_token = company_name.split()[0].lower()
            if company_token and company_token in lower.split("@")[-1]:
                s += 8
        if lower.split("@")[-1] in FREE_EMAIL_DOMAINS:
            s -= 5
        return s

    return max(emails, key=score)


# ── Parser (from OCR results) ──────────────────────────────────────────
def parse_experience_fields_from_ocr(ocr_results: list[OcrResult]) -> dict:
    """Extract experience letter fields from OCR results."""
    full_text = get_full_text(ocr_results)
    return _parse_from_text(full_text, ocr_results)


# ── Parser (from plain text — legacy compat) ───────────────────────────
def parse_experience_fields(text: str) -> dict:
    """Extract experience letter fields from plain text."""
    return _parse_from_text(text, [])


def _parse_from_text(text: str, ocr_results: list[OcrResult]) -> dict:
    fields: dict = {}

    # Company Name
    company_match = COMPANY_RE.search(text)
    company_name = company_match.group(1).strip() if company_match else None
    if not company_name:
        for line in text.splitlines()[:12]:
            if any(x in line for x in ["Ltd", "Limited", "Pvt", "LLP", "Inc", "Technologies", "Solutions"]):
                company_name = line.strip()[:120]
                break
    fields["company_name"] = company_name

    # Letterhead detection (top 15%)
    if ocr_results:
        top_text = get_text_in_region(ocr_results, y_start_pct=0.0, y_end_pct=0.15)
        fields["letterhead_detected"] = bool(company_name and company_name.lower() in top_text.lower())
    else:
        header_lines = "\n".join(text.splitlines()[:3]).lower()
        fields["letterhead_detected"] = bool(company_name and company_name.lower() in header_lines)

    # HR Email
    emails = EMAIL_RE.findall(text)
    fields["hr_email"] = _rank_email(emails, company_name)

    # Phone
    phones = PHONE_RE.findall(text)
    fields["phone"] = phones[0] if phones else None

    # Employee Name
    employee_name = None
    for pat in [
        r"(?:certify that|hereby certify that)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
        r"Dear\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
        r"(?:Mr\.|Ms\.|Mrs\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
        r"(?:employee|name)\s*[:\-]\s*([A-Za-z\s.]+)",
    ]:
        m = re.search(pat, text, re.I)
        if m:
            employee_name = m.group(1).strip()[:80]
            break
    if not employee_name and ocr_results:
        name_val = find_value_near_label(ocr_results, NAME_LABELS)
        if name_val:
            cleaned = re.sub(r"[^A-Za-z\s.]", "", name_val).strip()
            if len(cleaned) >= 3:
                employee_name = cleaned
    fields["employee_name"] = employee_name

    # Dates
    dates = DATE_RE.findall(text)
    fields["date_from"] = dates[0] if len(dates) > 0 else None
    fields["date_to"] = dates[1] if len(dates) > 1 else None

    # Also try spatial extraction for dates
    if ocr_results:
        if not fields["date_from"]:
            joining = find_value_near_label(ocr_results, JOINING_LABELS)
            if joining:
                dm = DATE_RE.search(joining)
                if dm:
                    fields["date_from"] = dm.group(0)
        if not fields["date_to"]:
            exit_date = find_value_near_label(ocr_results, EXIT_LABELS)
            if exit_date:
                dm = DATE_RE.search(exit_date)
                if dm:
                    fields["date_to"] = dm.group(0)

    # Designation
    designation = None
    des_match = re.search(r"(?:designation|position|role|title)\s*[:\-]?\s*([A-Za-z\s/]+)", text, re.I)
    if des_match:
        designation = des_match.group(1).strip()[:80]
    if not designation and ocr_results:
        des_val = find_value_near_label(ocr_results, DESIGNATION_LABELS)
        if des_val:
            designation = des_val[:80]
    fields["designation"] = designation

    # Department
    dept = None
    dept_match = re.search(r"(?:department|dept|division)\s*[:\-]?\s*([A-Za-z\s/]+)", text, re.I)
    if dept_match:
        dept = dept_match.group(1).strip()[:60]
    if not dept and ocr_results:
        dept_val = find_value_near_label(ocr_results, DEPARTMENT_LABELS)
        if dept_val:
            dept = dept_val[:60]
    fields["department"] = dept

    # Salary/CTC (optional)
    salary_match = re.search(r"(?:salary|ctc|compensation|remuneration)\s*[:\-]?\s*([\d,.\s]+(?:lpa|per annum|p\.a\.)?)", text, re.I)
    if salary_match:
        fields["salary"] = salary_match.group(1).strip()

    # Seal/Signature presence (bottom 25%)
    if ocr_results:
        bottom_text = get_text_in_region(ocr_results, y_start_pct=0.75, y_end_pct=1.0)
    else:
        lines = text.splitlines()
        bottom_text = "\n".join(lines[-(len(lines) // 4):]) if lines else ""

    fields["seal_present"] = bool(re.search(r"seal|stamp|मुद्रा", bottom_text, re.IGNORECASE))
    fields["signature_present"] = bool(re.search(r"signature|sign|authorized|हस्ताक्षर", bottom_text, re.IGNORECASE))

    return fields


# ── Validator ───────────────────────────────────────────────────────────
def is_free_email(email: str | None) -> bool:
    if not email:
        return False
    domain = email.split("@")[-1].lower()
    return domain in FREE_EMAIL_DOMAINS


def validate_experience(fields: dict, text: str, text_source: str, ocr_results: list[OcrResult]) -> tuple[float, list[str]]:
    """Validate experience letter. Returns (validation_score_0_to_20, flags)."""
    flags: list[str] = []
    checks_total = 0
    checks_passed = 0

    # Email presence
    checks_total += 1
    if fields.get("hr_email"):
        if is_free_email(fields["hr_email"]):
            flags.append("FREE_EMAIL")
            checks_passed += 0.5
        else:
            checks_passed += 1
    else:
        flags.append("NO_EMAIL")

    # Company name
    checks_total += 1
    if fields.get("company_name"):
        checks_passed += 1
    else:
        flags.append("NO_COMPANY")

    # Dates
    checks_total += 1
    if fields.get("date_from") or fields.get("date_to"):
        checks_passed += 1
    else:
        flags.append("MISSING_DATES")

    # Employee name
    checks_total += 1
    if fields.get("employee_name"):
        checks_passed += 1
    else:
        flags.append("MISSING_EMPLOYEE_NAME")

    # Experience keywords
    checks_total += 1
    lower = text.lower()
    if any(k in lower for k in EXP_KEYWORDS):
        checks_passed += 1
    else:
        flags.append("MISSING_EXPERIENCE_KEYWORDS")

    # Text source quality
    if text_source == "ocr":
        flags.append("SCANNED_DOCUMENT")
    elif text_source == "ocr_hindi":
        flags.append("HINDI_OCR_USED")

    # OCR confidence
    if ocr_results:
        avg_conf = get_average_confidence(ocr_results)
        if avg_conf < 0.4:
            flags.append("LOW_OCR_CONFIDENCE")

    validation_ratio = checks_passed / max(checks_total, 1)
    return validation_ratio * 20.0, flags


def score_experience(fields: dict, text: str, text_source: str) -> tuple[float, list[str]]:
    """Legacy compatibility — returns (score_0_100, flags)."""
    validation_score, flags = validate_experience(fields, text, text_source, [])
    return validation_score * 5.0, flags  # Scale to 0-100
