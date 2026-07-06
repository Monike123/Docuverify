"""Spatial field extraction engine — replaces YOLO detection.

Uses OCR bounding box positions + regex to locate and extract fields.
"""

from __future__ import annotations

import re
from ml_utils.ocr import OcrResult, group_by_lines


# ── Core Spatial Helpers ────────────────────────────────────────────────
def _image_dimensions(results: list[OcrResult]) -> tuple[int, int]:
    """Estimate image dimensions from OCR bounding boxes."""
    if not results:
        return (1, 1)
    max_x = max(max(p[0] for p in r.bbox) for r in results)
    max_y = max(max(p[1] for p in r.bbox) for r in results)
    return (max(max_x, 1), max(max_y, 1))


def find_by_regex(results: list[OcrResult], pattern: str, flags: int = 0) -> list[tuple[str, OcrResult]]:
    """Find all OCR blocks whose text matches a regex pattern."""
    compiled = re.compile(pattern, flags)
    matches: list[tuple[str, OcrResult]] = []
    for r in results:
        m = compiled.search(r.text)
        if m:
            matches.append((m.group(0), r))
    return matches


def find_keyword(results: list[OcrResult], keywords: list[str]) -> OcrResult | None:
    """Find first OCR block containing any of the keywords (case-insensitive)."""
    lower_kw = [k.lower() for k in keywords]
    for r in results:
        text_lower = r.text.lower()
        for kw in lower_kw:
            if kw in text_lower:
                return r
    return None


def find_value_near_label(
    results: list[OcrResult],
    label_keywords: list[str],
    direction: str = "right_or_below",
    max_distance_pct: float = 0.15,
) -> str | None:
    """Find the text block nearest to a label keyword.

    direction: 'right', 'below', 'right_or_below'
    max_distance_pct: max distance as fraction of image dimension
    """
    label_block = find_keyword(results, label_keywords)
    if label_block is None:
        return None

    img_w, img_h = _image_dimensions(results)
    lx1, ly1, lx2, ly2 = label_block.rect
    max_dx = img_w * max_distance_pct
    max_dy = img_h * max_distance_pct

    candidates: list[tuple[float, OcrResult]] = []

    for r in results:
        if r is label_block:
            continue
        rx1, ry1, rx2, ry2 = r.rect

        if direction in ("right", "right_or_below"):
            # Block is to the right and roughly same vertical position
            if rx1 >= lx2 - 10 and abs(r.center_y - label_block.center_y) < max_dy:
                dist = rx1 - lx2
                if dist < max_dx * 3:  # more lenient horizontally
                    candidates.append((dist, r))

        if direction in ("below", "right_or_below"):
            # Block is below and roughly same horizontal position
            if ry1 >= ly2 - 10 and abs(r.center_x - label_block.center_x) < max_dx * 2:
                dist = ry1 - ly2
                if dist < max_dy * 2:
                    candidates.append((dist + 10000, r))  # prefer right over below

    if not candidates:
        # Fallback: check if label text contains value after colon
        colon_match = re.search(r'[:\-]\s*(.+)', label_block.text)
        if colon_match:
            value = colon_match.group(1).strip()
            if value:
                return value
        return None

    candidates.sort(key=lambda x: x[0])
    return candidates[0][1].text


def get_text_in_region(
    results: list[OcrResult],
    y_start_pct: float = 0.0,
    y_end_pct: float = 1.0,
    x_start_pct: float = 0.0,
    x_end_pct: float = 1.0,
) -> str:
    """Get all text in a rectangular region (percentages of image dimensions)."""
    img_w, img_h = _image_dimensions(results)
    y_start = img_h * y_start_pct
    y_end = img_h * y_end_pct
    x_start = img_w * x_start_pct
    x_end = img_w * x_end_pct

    region_results = [
        r for r in results
        if y_start <= r.center_y <= y_end and x_start <= r.center_x <= x_end
    ]
    lines = group_by_lines(region_results)
    return "\n".join(" ".join(r.text for r in line) for line in lines)


def get_all_text_blocks_in_region(
    results: list[OcrResult],
    y_start_pct: float = 0.0,
    y_end_pct: float = 1.0,
    x_start_pct: float = 0.0,
    x_end_pct: float = 1.0,
) -> list[OcrResult]:
    """Get all OCR blocks in a rectangular region."""
    img_w, img_h = _image_dimensions(results)
    y_start = img_h * y_start_pct
    y_end = img_h * y_end_pct
    x_start = img_w * x_start_pct
    x_end = img_w * x_end_pct

    return [
        r for r in results
        if y_start <= r.center_y <= y_end and x_start <= r.center_x <= x_end
    ]


def get_nearby_text(
    results: list[OcrResult],
    anchor: OcrResult,
    direction: str = "below",
    max_blocks: int = 5,
    max_distance_pct: float = 0.2,
) -> list[OcrResult]:
    """Get text blocks near an anchor block in a given direction."""
    img_w, img_h = _image_dimensions(results)
    ax1, ay1, ax2, ay2 = anchor.rect
    max_dist = img_h * max_distance_pct if direction in ("below", "above") else img_w * max_distance_pct

    candidates: list[tuple[float, OcrResult]] = []
    for r in results:
        if r is anchor:
            continue
        rx1, ry1, rx2, ry2 = r.rect

        if direction == "below" and ry1 >= ay2 - 5:
            dist = ry1 - ay2
            if dist < max_dist:
                candidates.append((dist, r))
        elif direction == "right" and rx1 >= ax2 - 5:
            dist = rx1 - ax2
            if dist < max_dist and abs(r.center_y - anchor.center_y) < anchor.height * 1.5:
                candidates.append((dist, r))

    candidates.sort(key=lambda x: x[0])
    return [c[1] for c in candidates[:max_blocks]]


# ── Document-Specific Extraction Router ─────────────────────────────────
def extract_fields(ocr_results: list[OcrResult], doc_type: str) -> dict:
    """Route to the correct document-specific extractor."""
    if doc_type == "aadhaar":
        from ml_utils.validators.aadhaar import parse_aadhaar_fields
        return parse_aadhaar_fields(ocr_results)
    elif doc_type == "pan":
        from ml_utils.validators.pan import parse_pan_fields
        return parse_pan_fields(ocr_results)
    elif doc_type == "caste":
        from ml_utils.validators.caste import parse_caste_fields_from_ocr
        return parse_caste_fields_from_ocr(ocr_results)
    elif doc_type == "experience":
        from ml_utils.validators.experience import parse_experience_fields_from_ocr
        return parse_experience_fields_from_ocr(ocr_results)
    elif doc_type == "education":
        from ml_utils.validators.education import parse_education_fields
        return parse_education_fields(ocr_results)
    elif doc_type == "resume":
        from ml_utils.validators.resume import parse_resume_fields
        return parse_resume_fields(ocr_results)
    else:
        from ml_utils.validators.general import parse_general_fields
        return parse_general_fields(ocr_results)
