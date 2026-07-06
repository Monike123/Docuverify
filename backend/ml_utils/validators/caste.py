"""Caste certificate field extraction and validation — pure OCR-based."""

from __future__ import annotations

import re
from ml_utils.ocr import OcrResult, get_full_text, get_average_confidence
from ml_utils.extract import find_value_near_label, get_text_in_region, find_by_regex

DATE_RE = re.compile(
    r"\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|"
    r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}",
    re.I,
)

CASTE_KEYWORDS = ["caste", "category", "scheduled", "backward", "certificate", "जाति", "प्रमाणपत्र"]
CERT_KEYWORDS = ["certificate", "certify", "issued", "government", "govt", "प्रमाणपत्र"]
CATEGORY_PATTERNS = [
    r"(?:caste|category)\s*[:\-]\s*([A-Za-z\s]+)",
    r"(Scheduled Caste|Scheduled Tribe|Other Backward Class|OBC|SC|ST|General|EWS|NT|DT|VJ|SBC)",
]

NAME_LABELS = ["name", "applicant", "candidate", "नाम", "अर्जदार"]
FATHER_LABELS = ["father", "father's name", "पिता", "s/o", "d/o", "w/o"]
AUTHORITY_LABELS = ["authority", "issued by", "tahsildar", "collector", "प्राधिकारी"]
DISTRICT_LABELS = ["district", "taluka", "जिल्हा", "तालुका"]
STATE_LABELS = ["state", "राज्य"]


# ── Parser (from OCR results) ──────────────────────────────────────────
def parse_caste_fields_from_ocr(ocr_results: list[OcrResult]) -> dict:
    """Extract caste certificate fields from OCR results."""
    full_text = get_full_text(ocr_results)
    return _parse_from_text(full_text, ocr_results)


# ── Parser (from plain text — legacy compat) ───────────────────────────
def parse_caste_fields(text: str) -> dict:
    """Extract caste certificate fields from plain text."""
    return _parse_from_text(text, [])


def _parse_from_text(text: str, ocr_results: list[OcrResult]) -> dict:
    fields: dict = {}

    # Certificate number
    cert_match = re.search(r"(?:cert(?:ificate)?\s*(?:no|number|#)?[:\s]*)([A-Z0-9/\-]+)", text, re.I)
    if cert_match:
        fields["certificate_number"] = cert_match.group(1).strip()

    # Issue date
    dates = DATE_RE.findall(text)
    if dates:
        fields["issue_date"] = dates[0]

    # Caste category
    for pat in CATEGORY_PATTERNS:
        m = re.search(pat, text, re.I)
        if m:
            fields["caste_category"] = m.group(1).strip()
            break

    # Applicant name
    if ocr_results:
        name = find_value_near_label(ocr_results, NAME_LABELS)
        if name:
            cleaned = re.sub(r"[^A-Za-z\s.]", "", name).strip()
            if len(cleaned) >= 2:
                fields["applicant_name"] = cleaned
    if "applicant_name" not in fields:
        name_match = re.search(r"(?:name|applicant)\s*[:\-]\s*([A-Za-z\s.]+)", text, re.I)
        if name_match:
            fields["applicant_name"] = name_match.group(1).strip()[:80]

    # Father's name
    if ocr_results:
        father = find_value_near_label(ocr_results, FATHER_LABELS)
        if father:
            cleaned = re.sub(r"[^A-Za-z\s.]", "", father).strip()
            if len(cleaned) >= 2:
                fields["father_name"] = cleaned
    if "father_name" not in fields:
        father_match = re.search(r"(?:father|s/o|d/o|w/o)\s*[:\-]?\s*([A-Za-z\s.]+)", text, re.I)
        if father_match:
            fields["father_name"] = father_match.group(1).strip()[:80]

    # Issuing authority (usually in first few lines)
    if ocr_results:
        authority = find_value_near_label(ocr_results, AUTHORITY_LABELS)
        if authority:
            fields["issuing_authority"] = authority[:120]
    if "issuing_authority" not in fields:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for ln in lines[:8]:
            if any(k in ln.lower() for k in ["government", "govt", "authority", "tahsildar", "collector"]):
                fields["issuing_authority"] = ln[:120]
                break

    # District
    if ocr_results:
        district = find_value_near_label(ocr_results, DISTRICT_LABELS)
        if district:
            fields["district"] = re.sub(r"[^A-Za-z\s]", "", district).strip()
    if "district" not in fields:
        dist_match = re.search(r"(?:district|taluka)\s*[:\-]\s*([A-Za-z\s]+)", text, re.I)
        if dist_match:
            fields["district"] = dist_match.group(1).strip()

    # State
    if ocr_results:
        state = find_value_near_label(ocr_results, STATE_LABELS)
        if state:
            fields["state"] = re.sub(r"[^A-Za-z\s]", "", state).strip()

    # Seal/Signature presence (bottom 25%)
    if ocr_results:
        bottom_text = get_text_in_region(ocr_results, y_start_pct=0.75, y_end_pct=1.0)
    else:
        lines = text.splitlines()
        bottom_text = "\n".join(lines[-(len(lines) // 4):]) if lines else ""

    fields["seal_present"] = bool(re.search(r"seal|मुद्रा|मोहर", bottom_text, re.IGNORECASE))
    fields["signature_present"] = bool(re.search(r"signature|sign|हस्ताक्षर", bottom_text, re.IGNORECASE))

    return fields


# ── Validator ───────────────────────────────────────────────────────────
def validate_caste(fields: dict, text: str, ocr_results: list[OcrResult]) -> tuple[float, list[str]]:
    """Validate caste certificate. Returns (validation_score_0_to_20, flags)."""
    flags: list[str] = []
    checks_total = 0
    checks_passed = 0
    lower = text.lower()

    # Keyword presence
    checks_total += 1
    if any(k in lower for k in CASTE_KEYWORDS):
        checks_passed += 1
    else:
        flags.append("MISSING_CASTE_KEYWORD")

    checks_total += 1
    if any(k in lower for k in CERT_KEYWORDS):
        checks_passed += 1
    else:
        flags.append("MISSING_CERTIFICATE_KEYWORD")

    # Required fields
    for req in ["applicant_name", "caste_category"]:
        checks_total += 1
        if fields.get(req):
            checks_passed += 1
        else:
            flags.append(f"MISSING_{req.upper()}")

    # Optional fields bonus
    optional_filled = sum(1 for k in ["certificate_number", "issue_date", "issuing_authority", "district", "father_name"]
                         if fields.get(k))
    checks_total += 3
    checks_passed += min(3, optional_filled)

    # OCR confidence
    if ocr_results:
        avg_conf = get_average_confidence(ocr_results)
        if avg_conf < 0.4:
            flags.append("LOW_OCR_CONFIDENCE")

    validation_ratio = checks_passed / max(checks_total, 1)
    return validation_ratio * 20.0, flags


def redact_aadhaar_like(text: str) -> str:
    """Redact any Aadhaar-like numbers in text."""
    return re.sub(r"\b\d{4}\s?\d{4}\s?\d{4}\b", "[REDACTED]", text)
