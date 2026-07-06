"""Aadhaar card field extraction — improved accuracy, clean output."""

from __future__ import annotations
import re
from ml_utils.ocr import OcrResult, get_full_text, get_average_confidence
from ml_utils.extract import find_by_regex, find_value_near_label, find_keyword, get_text_in_region

# ── OCR character correction ─────────────────────────────────────────────
# EasyOCR commonly confuses these in names/numbers
_NUM_FIXES = str.maketrans({
    'O': '0', 'o': '0', 'I': '1', 'l': '1',
    'S': '5', 'Z': '2', 'B': '8', 'G': '6',
})

def _fix_number(text: str) -> str:
    return text.translate(_NUM_FIXES)

def _fix_name(text: str) -> str:
    """Title-case and remove noise from a name string."""
    cleaned = re.sub(r"[^A-Za-z\s.\-']", "", text).strip()
    # Remove isolated single chars that are noise
    parts = [p for p in cleaned.split() if len(p) > 1 or p == "A"]
    return " ".join(p.capitalize() for p in parts)

# ── Patterns ─────────────────────────────────────────────────────────────
AADHAAR_RE   = re.compile(r"\b(\d[\dO]{3}\s?[\dO]{4}\s?[\dO]{4})\b")
DOB_RE       = re.compile(r"\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})\b")
YEAR_RE      = re.compile(r"\b(19\d{2}|20[01]\d)\b")
PINCODE_RE   = re.compile(r"\b([1-9]\d{5})\b")
GENDER_RE    = re.compile(r"\b(Male|Female|Transgender|पुरुष|महिला)\b", re.IGNORECASE)

INDIAN_STATES = [
    "andhra pradesh","arunachal pradesh","assam","bihar","chhattisgarh","goa",
    "gujarat","haryana","himachal pradesh","jharkhand","karnataka","kerala",
    "madhya pradesh","maharashtra","manipur","meghalaya","mizoram","nagaland",
    "odisha","punjab","rajasthan","sikkim","tamil nadu","telangana","tripura",
    "uttar pradesh","uttarakhand","west bengal","delhi","chandigarh",
    "jammu","kashmir","ladakh",
]

NAME_LABELS    = ["name", "नाम", "naam"]
DOB_LABELS     = ["dob", "date of birth", "birth", "year of birth", "जन्म", "d.o.b", "जन्मतिथि"]
ADDRESS_LABELS = ["address", "पता", "addr", "s/o", "d/o", "w/o", "c/o"]

# Verhoeff tables
_D = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],
      [3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],
      [6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],
      [9,8,7,6,5,4,3,2,1,0]]
_P = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],
      [8,9,1,6,0,4,3,5,2,7],[9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],
      [2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]]
_INV = [0,4,3,2,1,5,6,7,8,9]

def _verhoeff_ok(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) != 12:
        return False
    c = 0
    for i, d in enumerate(reversed(digits)):
        c = _D[c][_P[i % 8][d]]
    return c == 0


# ── Field extraction ─────────────────────────────────────────────────────
def parse_aadhaar_fields(ocr_results: list[OcrResult]) -> dict:
    full_text = get_full_text(ocr_results)
    fields: dict = {}

    # ── Aadhaar Number ──────────────────────────────────────────────────
    # Search OCR results with O→0 correction
    for r in ocr_results:
        corrected = _fix_number(r.text)
        m = AADHAAR_RE.search(corrected)
        if m:
            raw = re.sub(r"\s", "", m.group(1)).replace('O','0')
            if len(raw) == 12 and raw.isdigit() and raw[0] != '0':
                fields["aadhaar_number_raw"] = raw
                break

    # Masked Aadhaar fallback
    if "aadhaar_number_raw" not in fields:
        masked = re.search(r"[Xx]{4}\s?[Xx]{4}\s?(\d{4})", full_text)
        if masked:
            fields["aadhaar_number_raw"] = f"XXXX-XXXX-{masked.group(1)}"
            fields["is_masked"] = True

    # ── Name ────────────────────────────────────────────────────────────
    name = find_value_near_label(ocr_results, NAME_LABELS)
    if name:
        fixed = _fix_name(name)
        if len(fixed) >= 3 and re.search(r"[A-Za-z]", fixed):
            fields["name"] = fixed

    if "name" not in fields:
        # Fallback: first all-caps or title-case line in top 45% that looks like a name
        top = get_text_in_region(ocr_results, y_start_pct=0.1, y_end_pct=0.55)
        for line in top.split("\n"):
            cleaned = re.sub(r"[^A-Za-z\s.\-']", "", line).strip()
            parts = cleaned.split()
            if 2 <= len(parts) <= 5 and all(len(p) >= 2 for p in parts):
                # Looks like a name (2-5 words, each 2+ chars)
                candidate = _fix_name(cleaned)
                if candidate and not any(w.lower() in ("government","india","uidai","unique") for w in parts):
                    fields["name"] = candidate
                    break

    # ── Date of Birth ───────────────────────────────────────────────────
    dob_raw = find_value_near_label(ocr_results, DOB_LABELS)
    if dob_raw:
        m = DOB_RE.search(dob_raw)
        if m:
            fields["date_of_birth"] = m.group(1)

    if "date_of_birth" not in fields:
        all_dobs = DOB_RE.findall(full_text)
        if all_dobs:
            fields["date_of_birth"] = all_dobs[0]
        else:
            years = YEAR_RE.findall(full_text)
            if years:
                fields["year_of_birth"] = years[0]

    # ── Gender ──────────────────────────────────────────────────────────
    g_match = GENDER_RE.search(full_text)
    if g_match:
        g = g_match.group(1).strip()
        if g in ("पुरुष",):
            fields["gender"] = "Male"
        elif g in ("महिला",):
            fields["gender"] = "Female"
        else:
            fields["gender"] = g.capitalize()

    # ── Address ─────────────────────────────────────────────────────────
    addr_block = find_keyword(ocr_results, ADDRESS_LABELS)
    if addr_block:
        from ml_utils.extract import get_nearby_text
        nearby = get_nearby_text(ocr_results, addr_block, direction="below", max_blocks=7)
        raw_addr = " ".join([addr_block.text] + [r.text for r in nearby])
        raw_addr = re.sub(r"^(?:address|पता|s/o|d/o|w/o|c/o)\s*[:\-]?\s*", "", raw_addr, flags=re.IGNORECASE).strip()
        if len(raw_addr) > 10:
            fields["address"] = raw_addr
    else:
        bottom = get_text_in_region(ocr_results, y_start_pct=0.55, y_end_pct=1.0)
        if bottom and len(bottom) > 15:
            fields["address"] = bottom.strip()

    # ── PIN Code ────────────────────────────────────────────────────────
    search_text = fields.get("address", full_text)
    pin_m = PINCODE_RE.search(search_text)
    if pin_m:
        fields["pincode"] = pin_m.group(1)

    # ── State ───────────────────────────────────────────────────────────
    lower_text = full_text.lower()
    for state in INDIAN_STATES:
        if state in lower_text:
            fields["state"] = state.title()
            break

    return fields


# ── Validator ─────────────────────────────────────────────────────────────
REQUIRED = {"aadhaar_number_raw", "name", "date_of_birth"}

def validate_aadhaar(fields: dict, ocr_results: list[OcrResult]) -> tuple[float, list[str]]:
    flags: list[str] = []
    passed = 0
    total = 0

    for req in REQUIRED:
        total += 1
        if fields.get(req):
            passed += 1
        else:
            flags.append(f"MISSING_{req.upper()}")

    # Aadhaar number checks
    num = fields.get("aadhaar_number_raw", "")
    clean = re.sub(r"[\s\-X]", "", num)
    if clean and clean.isdigit():
        total += 1
        if len(clean) == 12:
            passed += 1
            total += 1
            if _verhoeff_ok(clean):
                passed += 1
            else:
                flags.append("AADHAAR_CHECKSUM_MISMATCH")
        else:
            flags.append("AADHAAR_NUMBER_INCOMPLETE")

    # DOB format
    dob = fields.get("date_of_birth", "")
    if dob:
        total += 1
        if DOB_RE.search(dob):
            passed += 1
        else:
            flags.append("INVALID_DATE_FORMAT")

    # Pincode
    pin = fields.get("pincode", "")
    if pin:
        total += 1
        if re.fullmatch(r"[1-9]\d{5}", pin):
            passed += 1
        else:
            flags.append("INVALID_PINCODE")

    # OCR confidence
    avg_conf = get_average_confidence(ocr_results)
    if avg_conf < 0.40:
        flags.append("LOW_OCR_CONFIDENCE")

    ratio = passed / max(total, 1)
    return ratio * 20.0, flags


# ── Clean output for display ─────────────────────────────────────────────
# Fields to NEVER show to the user (internal/technical)
_HIDDEN_FIELDS = {"is_masked", "aadhaar_number_raw", "aadhaar_masked"}

# Human-readable label mapping
FIELD_LABELS = {
    "name":              "Full Name",
    "date_of_birth":     "Date of Birth",
    "year_of_birth":     "Year of Birth",
    "gender":            "Gender",
    "aadhaar_number_display": "Aadhaar Number",
    "address":           "Address",
    "pincode":           "PIN Code",
    "state":             "State",
}

def build_extracted_output(fields: dict) -> dict:
    """Return only user-facing fields with clean labels and redacted Aadhaar."""
    output = {}

    # Aadhaar display — always redact, show only last 4 digits
    raw = fields.get("aadhaar_number_raw", "")
    clean_raw = re.sub(r"[\s\-]", "", raw)
    if clean_raw and clean_raw.isdigit() and len(clean_raw) == 12:
        output["aadhaar_number_display"] = f"XXXX XXXX {clean_raw[-4:]}"
    elif fields.get("is_masked"):
        # Already masked from source
        m = re.search(r"(\d{4})$", raw)
        if m:
            output["aadhaar_number_display"] = f"XXXX XXXX {m.group(1)}"

    # Copy user-facing fields
    for key in ["name", "date_of_birth", "year_of_birth", "gender", "address", "pincode", "state"]:
        if fields.get(key):
            output[key] = fields[key]

    return output
