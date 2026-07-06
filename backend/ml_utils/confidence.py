"""Confidence scoring and decision engine — explainable decisions."""

from __future__ import annotations

from ml_utils.ocr import OcrResult, get_average_confidence

# Legacy constants used by fft_detect.py and edge_detect.py
FFT_MAX = 8.0
EDGE_MAX = 7.0

# ── Required fields per doc type ────────────────────────────────────────
REQUIRED_FIELDS: dict[str, set[str]] = {
    "aadhaar": {"aadhaar_number", "name", "dob"},
    "pan": {"pan_number", "name"},
    "caste": {"applicant_name", "caste_category"},
    "experience": {"company_name", "employee_name"},
    "education": {"candidate_name", "institute", "degree"},
    "resume": {"name", "email"},
    "general": set(),
}


# ── Score Components ────────────────────────────────────────────────────
def compute_ocr_score(ocr_results: list[OcrResult]) -> float:
    """OCR quality: avg confidence × 35 (max 35)."""
    avg = get_average_confidence(ocr_results)
    return round(min(35.0, avg * 35.0), 1)


def compute_field_score(fields: dict, doc_type: str) -> float:
    """Field completeness: (found / required) × 30 (max 30)."""
    required = REQUIRED_FIELDS.get(doc_type, set())
    if not required:
        # For general docs, count any detected fields
        detected_count = len(fields)
        return round(min(30.0, (detected_count / 5.0) * 30.0), 1)

    found = sum(1 for f in required if fields.get(f))
    ratio = found / len(required)
    return round(ratio * 30.0, 1)


def compute_validation_score(validation_score: float) -> float:
    """Already computed by validators as 0-20. Just pass through."""
    return round(min(20.0, max(0.0, validation_score)), 1)


def compute_image_score(fft_score: float | None, edge_score: float | None) -> float:
    """Image quality from forgery detection (max 15).

    fft_score is 0-15 from fft_detect (higher = more authentic).
    edge_score is 0-12 from edge_detect (higher = more consistent).
    We normalize to max 15.
    """
    fft = fft_score if fft_score is not None else 8.0
    edge = edge_score if edge_score is not None else 7.0
    # fft max 8, edge max 7 → total 15
    return round(min(15.0, fft + edge), 1)


def compute_final_score(
    ocr_quality: float,
    field_completeness: float,
    validation: float,
    image_quality: float,
) -> float:
    """Sum all components, cap at 100."""
    return round(min(100.0, ocr_quality + field_completeness + validation + image_quality), 1)


# ── Decision ────────────────────────────────────────────────────────────
STATUS_THRESHOLDS = [
    (90, "Auto-Verified"),
    (75, "Verified"),
    (50, "Manual Review Required"),
    (25, "Low Confidence"),
    (0, "Rejected"),
]


def decide_status(score: float, flags: list[str]) -> str:
    """Map score + flags to a decision status."""
    # Critical flags force rejection regardless of score
    critical_flags = {"VERHOEFF_CHECKSUM_FAILED", "INVALID_PAN_FORMAT", "TEXT_EXTRACT_FAILED"}
    if any(f in critical_flags for f in flags):
        return "Rejected"

    for threshold, status in STATUS_THRESHOLDS:
        if score >= threshold:
            return status
    return "Rejected"


def build_score_breakdown(
    ocr_results: list[OcrResult],
    fields: dict,
    doc_type: str,
    validation_score: float,
    fft_score: float | None,
    edge_score: float | None,
) -> dict:
    """Compute all scores and return full breakdown dict."""
    ocr_q = compute_ocr_score(ocr_results)
    field_c = compute_field_score(fields, doc_type)
    valid_s = compute_validation_score(validation_score)
    img_q = compute_image_score(fft_score, edge_score)
    final = compute_final_score(ocr_q, field_c, valid_s, img_q)

    return {
        "ocr_quality": ocr_q,
        "field_completeness": field_c,
        "validation": valid_s,
        "image_quality": img_q,
        "overall": final,
    }
