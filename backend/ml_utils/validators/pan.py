"""PAN card field extraction and validation — pure OCR-based."""

from __future__ import annotations

import re
from ml_utils.ocr import OcrResult, get_full_text, get_average_confidence
from ml_utils.extract import find_by_regex, find_value_near_label, get_text_in_region

# ── Patterns ────────────────────────────────────────────────────────────
PAN_RE = re.compile(r"[A-Z]{5}\d{4}[A-Z]", re.IGNORECASE)
DOB_RE = re.compile(r"\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})\b")
NAME_LABELS = ["name", "नाम", "naam"]
FATHER_LABELS = ["father", "father's name", "पिता", "father name"]
DOB_LABELS = ["date of birth", "dob", "d.o.b", "birth", "जन्म तिथि"]


def _fix_pan_chars(value: str) -> str:
    """Fix common OCR misreads in PAN numbers."""
    if len(value) < 10:
        return value
    chars = list(value[:10])
    # Positions 0-4 should be letters
    for i in range(5):
        if chars[i].isdigit():
            chars[i] = {"0": "O", "1": "I", "5": "S", "8": "B"}.get(chars[i], chars[i])
    # Positions 5-8 should be digits
    for i in range(5, 9):
        if not chars[i].isdigit():
            chars[i] = {"O": "0", "I": "1", "S": "5", "B": "8", "l": "1", "o": "0"}.get(chars[i], chars[i])
    # Position 9 should be a letter
    if len(chars) == 10 and not chars[9].isalpha():
        chars[9] = {"0": "O", "1": "I"}.get(chars[9], chars[9])
    return "".join(chars)


def _cleanup_pan_text(text: str) -> str:
    """Clean and extract PAN number from OCR text."""
    compact = text.upper().replace(" ", "").replace("-", "").replace(".", "")
    match = PAN_RE.search(compact)
    if match:
        return _fix_pan_chars(match.group(0).upper())
    # Try with OCR error correction
    for candidate in re.findall(r"[A-Z0-9]{10}", compact):
        fixed = _fix_pan_chars(candidate)
        if PAN_RE.fullmatch(fixed):
            return fixed
    if len(compact) >= 10:
        return _fix_pan_chars(compact[-10:])
    return compact


# ── Parser ──────────────────────────────────────────────────────────────
def parse_pan_fields(ocr_results: list[OcrResult]) -> dict:
    """Extract PAN card fields from OCR results."""
    full_text = get_full_text(ocr_results)
    fields: dict = {}

    # PAN Number — regex on all text
    pan_matches = find_by_regex(ocr_results, r"[A-Z0-9]{5}\s?[A-Z0-9]{4}\s?[A-Z0-9]")
    pan_found = False
    for raw_match, _ in pan_matches:
        cleaned = _cleanup_pan_text(raw_match)
        if PAN_RE.fullmatch(cleaned):
            fields["pan_number"] = cleaned
            pan_found = True
            break

    if not pan_found:
        # Try on full text
        compact = re.sub(r"\s", "", full_text.upper())
        match = PAN_RE.search(compact)
        if match:
            fields["pan_number"] = _fix_pan_chars(match.group(0))
        else:
            for candidate in re.findall(r"[A-Z0-9]{10}", compact):
                fixed = _fix_pan_chars(candidate)
                if PAN_RE.fullmatch(fixed):
                    fields["pan_number"] = fixed
                    break

    # Name
    name = find_value_near_label(ocr_results, NAME_LABELS)
    if name:
        cleaned = re.sub(r"[^A-Za-z\s.]", "", name).strip()
        if len(cleaned) >= 2 and not PAN_RE.search(cleaned):
            fields["name"] = cleaned

    if "name" not in fields:
        # PAN cards: name is usually the 2nd or 3rd line from top
        top_text = get_text_in_region(ocr_results, y_start_pct=0.15, y_end_pct=0.50)
        for line in top_text.split("\n"):
            cleaned = re.sub(r"[^A-Za-z\s.]", "", line).strip()
            if (len(cleaned) >= 4 and " " in cleaned
                    and not any(k in cleaned.lower() for k in ["income", "tax", "govt", "india", "permanent"])):
                fields["name"] = cleaned
                break

    # Father's Name
    father = find_value_near_label(ocr_results, FATHER_LABELS)
    if father:
        cleaned = re.sub(r"[^A-Za-z\s.]", "", father).strip()
        if len(cleaned) >= 2:
            fields["father_name"] = cleaned

    # DOB
    dob = find_value_near_label(ocr_results, DOB_LABELS)
    if dob:
        dob_match = DOB_RE.search(dob)
        if dob_match:
            fields["dob"] = dob_match.group(1)
    if "dob" not in fields:
        all_dobs = DOB_RE.findall(full_text)
        if all_dobs:
            fields["dob"] = all_dobs[0]

    # Signature presence (bottom region text)
    bottom_text = get_text_in_region(ocr_results, y_start_pct=0.75, y_end_pct=1.0)
    fields["signature_present"] = bool(
        re.search(r"signature|sign|हस्ताक्षर", bottom_text, re.IGNORECASE)
    )

    return fields


# ── Validator ───────────────────────────────────────────────────────────
REQUIRED_FIELDS = {"pan_number", "name"}


def validate_pan(fields: dict, ocr_results: list[OcrResult]) -> tuple[float, list[str]]:
    """Validate PAN extraction. Returns (validation_score_0_to_20, flags)."""
    flags: list[str] = []
    checks_total = 0
    checks_passed = 0

    # Required fields
    for req in REQUIRED_FIELDS:
        checks_total += 1
        if fields.get(req):
            checks_passed += 1
        else:
            flags.append(f"MISSING_{req.upper()}")

    # PAN format validation
    pan = fields.get("pan_number", "")
    if pan:
        checks_total += 1
        if PAN_RE.fullmatch(pan):
            checks_passed += 1
            fields["pan_validated"] = True
        else:
            flags.append("INVALID_PAN_FORMAT")
            fields["pan_validated"] = False
    else:
        flags.append("NO_PAN_OCR")
        fields["pan_validated"] = False

    # DOB format
    dob = fields.get("dob", "")
    if dob:
        checks_total += 1
        if DOB_RE.search(dob):
            checks_passed += 1
        else:
            flags.append("INVALID_DOB_FORMAT")

    # OCR confidence
    avg_conf = get_average_confidence(ocr_results)
    if avg_conf < 0.4:
        flags.append("LOW_OCR_CONFIDENCE")

    validation_ratio = checks_passed / max(checks_total, 1)
    return validation_ratio * 20.0, flags
