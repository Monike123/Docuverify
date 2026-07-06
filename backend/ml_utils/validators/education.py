"""Education certificate field extraction and validation."""

from __future__ import annotations

import re
from ml_utils.ocr import OcrResult, get_full_text, get_average_confidence
from ml_utils.extract import find_value_near_label, get_text_in_region, find_by_regex

DEGREE_PATTERNS = [
    r"(B\.?\s?Tech|M\.?\s?Tech|B\.?\s?E\.?|M\.?\s?E\.?|B\.?\s?Sc|M\.?\s?Sc|B\.?\s?Com|M\.?\s?Com|"
    r"B\.?\s?A\.?|M\.?\s?A\.?|MBA|BBA|BCA|MCA|Ph\.?\s?D|B\.?\s?Ed|M\.?\s?Ed|Diploma|"
    r"B\.?\s?Pharm|M\.?\s?Pharm|MBBS|MD|B\.?\s?Arch|LLB|LLM|B\.?\s?Des|M\.?\s?Des)",
]
DOB_RE = re.compile(r"\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})\b")
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
CGPA_RE = re.compile(r"(\d+\.?\d*)\s*(?:/\s*(?:10|4))?(?:\s*(?:CGPA|GPA|SGPA|CPI))?", re.I)
PERCENTAGE_RE = re.compile(r"(\d{1,3}\.?\d*)\s*%")
REG_RE = re.compile(r"(?:reg(?:istration)?|roll|enrollment|hall\s*ticket)\s*(?:no|number|#)?\s*[:\-]?\s*([A-Z0-9/\-]+)", re.I)

NAME_LABELS = ["name", "student", "candidate", "नाम"]
INSTITUTE_LABELS = ["institute", "institution", "college", "school", "संस्था"]
UNIVERSITY_LABELS = ["university", "board", "विश्वविद्यालय", "affiliated"]
DEGREE_LABELS = ["degree", "course", "programme", "program", "उपाधि"]
YEAR_LABELS = ["year", "passing", "convocation", "session", "batch"]
CGPA_LABELS = ["cgpa", "gpa", "percentage", "marks", "grade", "result"]
REG_LABELS = ["registration", "roll", "enrollment", "reg no", "hall ticket"]


def parse_education_fields(ocr_results: list[OcrResult]) -> dict:
    """Extract education certificate fields from OCR results."""
    full_text = get_full_text(ocr_results)
    fields: dict = {}

    # Candidate name
    name = find_value_near_label(ocr_results, NAME_LABELS)
    if name:
        cleaned = re.sub(r"[^A-Za-z\s.]", "", name).strip()
        if len(cleaned) >= 2:
            fields["candidate_name"] = cleaned

    # Institute (usually in top region)
    institute = find_value_near_label(ocr_results, INSTITUTE_LABELS)
    if institute and len(institute) >= 3:
        fields["institute"] = institute[:120]
    if "institute" not in fields:
        top_text = get_text_in_region(ocr_results, y_start_pct=0.0, y_end_pct=0.25)
        if top_text and len(top_text) > 5:
            # First long line is often the institute name
            for line in top_text.split("\n"):
                if len(line.strip()) > 10:
                    fields["institute"] = line.strip()[:120]
                    break

    # University
    university = find_value_near_label(ocr_results, UNIVERSITY_LABELS)
    if university and len(university) >= 3:
        fields["university"] = university[:120]

    # Degree
    for pat in DEGREE_PATTERNS:
        m = re.search(pat, full_text, re.I)
        if m:
            fields["degree"] = m.group(1).strip()
            break
    if "degree" not in fields:
        degree = find_value_near_label(ocr_results, DEGREE_LABELS)
        if degree:
            fields["degree"] = degree[:60]

    # Passing year
    year_val = find_value_near_label(ocr_results, YEAR_LABELS)
    if year_val:
        ym = YEAR_RE.search(year_val)
        if ym:
            fields["passing_year"] = ym.group(1)
    if "passing_year" not in fields:
        years = YEAR_RE.findall(full_text)
        if years:
            # Pick the most recent year
            fields["passing_year"] = max(years, key=int)

    # CGPA / Percentage
    pct_match = PERCENTAGE_RE.search(full_text)
    if pct_match:
        val = float(pct_match.group(1))
        if 0 < val <= 100:
            fields["percentage"] = f"{val}%"

    cgpa_val = find_value_near_label(ocr_results, CGPA_LABELS)
    if cgpa_val:
        cm = re.search(r"(\d+\.?\d*)", cgpa_val)
        if cm:
            val = float(cm.group(1))
            if 0 < val <= 10:
                fields["cgpa"] = str(val)
            elif 0 < val <= 100 and "percentage" not in fields:
                fields["percentage"] = f"{val}%"

    # Registration / Roll number
    reg_match = REG_RE.search(full_text)
    if reg_match:
        fields["registration_number"] = reg_match.group(1).strip()
    if "registration_number" not in fields:
        reg_val = find_value_near_label(ocr_results, REG_LABELS)
        if reg_val:
            # Extract alphanumeric part
            rm = re.search(r"([A-Z0-9/\-]{3,})", reg_val, re.I)
            if rm:
                fields["registration_number"] = rm.group(1)

    return fields


# ── Validator ───────────────────────────────────────────────────────────
REQUIRED = {"candidate_name", "institute", "degree"}


def validate_education(fields: dict, ocr_results: list[OcrResult]) -> tuple[float, list[str]]:
    """Validate education certificate. Returns (validation_score_0_to_20, flags)."""
    flags: list[str] = []
    checks_total = 0
    checks_passed = 0

    for req in REQUIRED:
        checks_total += 1
        if fields.get(req):
            checks_passed += 1
        else:
            flags.append(f"MISSING_{req.upper()}")

    # Optional fields
    optional_filled = sum(1 for k in ["passing_year", "cgpa", "percentage", "university", "registration_number"]
                         if fields.get(k))
    checks_total += 2
    checks_passed += min(2, optional_filled)

    if ocr_results:
        avg_conf = get_average_confidence(ocr_results)
        if avg_conf < 0.4:
            flags.append("LOW_OCR_CONFIDENCE")

    validation_ratio = checks_passed / max(checks_total, 1)
    return validation_ratio * 20.0, flags
