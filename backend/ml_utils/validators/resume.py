"""Resume/CV field extraction and validation."""

from __future__ import annotations

import re
from ml_utils.ocr import OcrResult, get_full_text, get_average_confidence
from ml_utils.extract import find_value_near_label, find_keyword, get_text_in_region, get_nearby_text

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+91[\s\-]?)?[6-9]\d{9}|\+?\d{1,3}[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}")
LINKEDIN_RE = re.compile(r"linkedin\.com/in/[\w\-]+", re.I)

SECTION_HEADERS = {
    "education": ["education", "academic", "qualification", "academics"],
    "experience": ["experience", "work experience", "employment", "professional experience", "work history"],
    "skills": ["skills", "technical skills", "core competencies", "technologies", "proficiencies"],
    "projects": ["projects", "personal projects", "key projects"],
    "certifications": ["certifications", "certificates", "awards", "achievements", "honors"],
    "summary": ["summary", "objective", "about me", "profile", "career objective"],
}


def _extract_section(full_text: str, section_keywords: list[str]) -> str:
    """Extract text under a section header until the next section."""
    lines = full_text.split("\n")
    capturing = False
    section_lines: list[str] = []
    all_headers = [kw for kws in SECTION_HEADERS.values() for kw in kws]

    for line in lines:
        lower = line.lower().strip()
        if any(kw in lower for kw in section_keywords) and len(lower) < 50:
            capturing = True
            continue
        if capturing:
            # Stop if we hit another section header
            if any(kw in lower for kw in all_headers) and len(lower) < 50:
                break
            if line.strip():
                section_lines.append(line.strip())

    return "\n".join(section_lines)


def parse_resume_fields(ocr_results: list[OcrResult]) -> dict:
    """Extract resume fields from OCR results."""
    full_text = get_full_text(ocr_results)
    fields: dict = {}

    # Name (usually the first/largest text at top)
    top_text = get_text_in_region(ocr_results, y_start_pct=0.0, y_end_pct=0.15)
    for line in top_text.split("\n"):
        cleaned = re.sub(r"[^A-Za-z\s.]", "", line).strip()
        if len(cleaned) >= 3 and " " in cleaned:
            # Likely a name — not an email or phone
            if not EMAIL_RE.search(line) and not PHONE_RE.search(line):
                fields["name"] = cleaned
                break

    # Email
    emails = EMAIL_RE.findall(full_text)
    if emails:
        fields["email"] = emails[0]

    # Phone
    phones = PHONE_RE.findall(full_text)
    if phones:
        fields["phone"] = phones[0]

    # LinkedIn
    linkedin = LINKEDIN_RE.search(full_text)
    if linkedin:
        fields["linkedin"] = linkedin.group(0)

    # Sections
    for section_key, section_kws in SECTION_HEADERS.items():
        content = _extract_section(full_text, section_kws)
        if content:
            fields[section_key] = content

    return fields


# ── Validator ───────────────────────────────────────────────────────────
def validate_resume(fields: dict, ocr_results: list[OcrResult]) -> tuple[float, list[str]]:
    """Validate resume extraction. Returns (validation_score_0_to_20, flags)."""
    flags: list[str] = []
    checks_total = 0
    checks_passed = 0

    for req in ["name", "email"]:
        checks_total += 1
        if fields.get(req):
            checks_passed += 1
        else:
            flags.append(f"MISSING_{req.upper()}")

    optional_filled = sum(1 for k in ["phone", "education", "experience", "skills"]
                         if fields.get(k))
    checks_total += 2
    checks_passed += min(2, optional_filled)

    if ocr_results:
        avg_conf = get_average_confidence(ocr_results)
        if avg_conf < 0.4:
            flags.append("LOW_OCR_CONFIDENCE")

    validation_ratio = checks_passed / max(checks_total, 1)
    return validation_ratio * 20.0, flags
