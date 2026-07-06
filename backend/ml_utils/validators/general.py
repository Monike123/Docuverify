"""General document field extraction — catch-all parser for unknown types."""

from __future__ import annotations

import re
from ml_utils.ocr import OcrResult, get_full_text, get_average_confidence

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+91[\s\-]?)?[6-9]\d{9}")
DATE_RE = re.compile(
    r"\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|"
    r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}",
    re.I,
)
KV_RE = re.compile(r"([A-Za-z\s]{2,30})\s*[:\-]\s*(.+)")


def parse_general_fields(ocr_results: list[OcrResult]) -> dict:
    """Extract whatever we can from an unknown document type."""
    full_text = get_full_text(ocr_results)
    fields: dict = {}

    # Emails
    emails = EMAIL_RE.findall(full_text)
    if emails:
        fields["emails"] = emails

    # Phones
    phones = PHONE_RE.findall(full_text)
    if phones:
        fields["phones"] = phones

    # Dates
    dates = DATE_RE.findall(full_text)
    if dates:
        fields["dates"] = dates

    # Key-value pairs
    kv_pairs: dict = {}
    for line in full_text.split("\n"):
        m = KV_RE.match(line.strip())
        if m:
            key = m.group(1).strip().lower().replace(" ", "_")
            value = m.group(2).strip()
            if len(key) >= 2 and len(value) >= 1:
                kv_pairs[key] = value
    if kv_pairs:
        fields["detected_fields"] = kv_pairs

    fields["full_text_preview"] = full_text[:500] if full_text else ""

    return fields


def validate_general(fields: dict, ocr_results: list[OcrResult]) -> tuple[float, list[str]]:
    """Minimal validation for unknown documents."""
    flags: list[str] = ["UNKNOWN_DOC_TYPE"]
    checks_total = 2
    checks_passed = 0

    if fields.get("detected_fields"):
        checks_passed += 1
    if fields.get("full_text_preview") and len(fields["full_text_preview"]) > 20:
        checks_passed += 1

    if ocr_results:
        avg_conf = get_average_confidence(ocr_results)
        if avg_conf < 0.4:
            flags.append("LOW_OCR_CONFIDENCE")

    validation_ratio = checks_passed / max(checks_total, 1)
    return validation_ratio * 20.0, flags
