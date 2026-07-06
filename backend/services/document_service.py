"""Unified document analysis pipeline — no YOLO, EasyOCR only."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

import cv2
import numpy as np

from config import MASKED_OUTPUT, ORIGINAL_UPLOADS
from ml_utils.confidence import build_score_breakdown, decide_status
from ml_utils.edge_detect import edge_inconsistency_score
from ml_utils.extract import extract_fields
from ml_utils.forgery_detector import detect_forgery
from ml_utils.fft_detect import fft_anomaly_score
from ml_utils.mask import mask_pii_on_image, save_masked_image
from ml_utils.ocr import OcrResult, get_full_text, get_average_confidence, ocr_multipass
from ml_utils.text_extractor import extract_with_ocr_results

logger = logging.getLogger("docverify.service")


def _image_to_base64(image_bgr: np.ndarray | None) -> str | None:
    """Encode a BGR image to base64 JPEG string for Supabase storage."""
    if image_bgr is None:
        return None
    try:
        _, buffer = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return base64.b64encode(buffer).decode("utf-8")
    except Exception:
        return None


def _file_to_base64(file_path: str) -> str | None:
    """Read a file and encode to base64."""
    try:
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None


def _save_original(file_path: str, doc_id: str) -> str | None:
    """Copy original upload to persistent storage for preview."""
    src = Path(file_path)
    if not src.exists():
        return None
    ORIGINAL_UPLOADS.mkdir(parents=True, exist_ok=True)
    dest = ORIGINAL_UPLOADS / f"{doc_id}{src.suffix}"
    try:
        import shutil
        shutil.copy2(str(src), str(dest))
        return str(dest)
    except Exception:
        return None


def _validate_for_doc_type(fields: dict, doc_type: str, text: str, text_source: str, ocr_results: list[OcrResult]) -> tuple[float, list[str]]:
    """Route to the correct validator and return (validation_score_0_to_20, flags)."""
    if doc_type == "aadhaar":
        from ml_utils.validators.aadhaar import validate_aadhaar
        return validate_aadhaar(fields, ocr_results)
    elif doc_type == "pan":
        from ml_utils.validators.pan import validate_pan
        return validate_pan(fields, ocr_results)
    elif doc_type == "caste":
        from ml_utils.validators.caste import validate_caste
        return validate_caste(fields, text, ocr_results)
    elif doc_type == "experience":
        from ml_utils.validators.experience import validate_experience
        return validate_experience(fields, text, text_source, ocr_results)
    elif doc_type == "education":
        from ml_utils.validators.education import validate_education
        return validate_education(fields, ocr_results)
    elif doc_type == "resume":
        from ml_utils.validators.resume import validate_resume
        return validate_resume(fields, ocr_results)
    else:
        from ml_utils.validators.general import validate_general
        return validate_general(fields, ocr_results)


def _clean_fields_for_display(fields: dict, doc_type: str) -> dict:
    """Return only user-facing fields, hiding internal/technical keys."""
    try:
        if doc_type == "aadhaar":
            from ml_utils.validators.aadhaar import build_extracted_output
            return build_extracted_output(fields)
        elif doc_type == "pan":
            # PAN: hide signature_present and pan_validated (internal)
            HIDDEN = {"signature_present", "pan_validated"}
            return {k: v for k, v in fields.items() if k not in HIDDEN}
        else:
            return fields
    except Exception:
        return fields


def analyze_document(doc_type: str, file_path: str, doc_id: str) -> dict:
    """One unified pipeline for ALL document types."""
    try:
        return _run_pipeline(doc_type, file_path, doc_id)
    except Exception as exc:
        logger.exception("Analysis failed for %s (%s)", doc_id, doc_type)
        return {
            "confidence_score": 0.0,
            "score_breakdown": {"ocr_quality": 0, "field_completeness": 0, "validation": 0, "image_quality": 0, "overall": 0},
            "flags": [f"ANALYSIS_ERROR: {type(exc).__name__}"],
            "extracted_fields": {},
            "full_text": "",
            "status": "Manual Review Required",
            "text_source": None,
            "masked_image_path": None,
            "ocr_confidence": 0.0,
            "original_path": None,
            "image_base64": None,
            "masked_image_base64": None,
        }


def _run_pipeline(doc_type: str, file_path: str, doc_id: str) -> dict:
    # 0. Save original for preview + encode to base64
    original_path = _save_original(file_path, doc_id)
    image_b64 = _file_to_base64(file_path)

    # 1. Extract text + OCR results + image
    text, text_source, ocr_results, image = extract_with_ocr_results(file_path)

    if not text.strip() and not ocr_results and image is None:
        return {
            "confidence_score": 0.0,
            "score_breakdown": {"ocr_quality": 0, "field_completeness": 0, "validation": 0, "image_quality": 0, "overall": 0},
            "flags": ["TEXT_EXTRACT_FAILED"],
            "extracted_fields": {},
            "full_text": "",
            "status": "Rejected",
            "text_source": text_source,
            "masked_image_path": None,
            "ocr_confidence": 0.0,
            "original_path": original_path,
            "image_base64": image_b64,
            "masked_image_base64": None,
            "forgery_score": 0.0,
        }

    # 2. OCR-based field extraction
    fields = extract_fields(ocr_results, doc_type) if ocr_results else {}
    if not ocr_results and text:
        if doc_type == "caste":
            from ml_utils.validators.caste import parse_caste_fields
            fields = parse_caste_fields(text)
        elif doc_type == "experience":
            from ml_utils.validators.experience import parse_experience_fields
            fields = parse_experience_fields(text)

    full_text = text if text else get_full_text(ocr_results)
    avg_conf = get_average_confidence(ocr_results) if ocr_results else 0.8

    # 3. ── GEMINI VISION ANALYSIS ──────────────────────────────────────────
    gemini_result = None
    gemini_forgery_score: float = 0.0
    gemini_flags: list[str] = []

    if image is not None:
        try:
            from ml_utils.gemini_analyzer import analyze_with_gemini, merge_fields
            # Pass PDF text layer if available — Gemini uses it as extra context
            pdf_text_hint = text if text_source == "pdf_text" else None
            gemini_result = analyze_with_gemini(image, doc_type, pdf_text=pdf_text_hint)

            if gemini_result.used_gemini:
                # Merge: Gemini fields override OCR for same keys, OCR fills gaps
                fields = merge_fields(gemini_result.fields, fields, doc_type)
                gemini_forgery_score = gemini_result.forgery_score

                if gemini_result.is_suspicious:
                    gemini_flags = ["POSSIBLE_DOCUMENT_MANIPULATION"]
                    logger.info("Gemini forgery: suspicious doc=%s score=%.1f reason=%s",
                                doc_id, gemini_forgery_score, gemini_result.forgery_reason)
                else:
                    logger.info("Gemini forgery: clean doc=%s score=%.1f", doc_id, gemini_forgery_score)
            else:
                logger.info("Gemini unavailable (%s) — OCR-only mode", gemini_result.error)
        except Exception:
            logger.warning("Gemini integration failed for %s — using OCR only", doc_id)

    # 4. Rule-based validation
    validation_score, validation_flags = _validate_for_doc_type(fields, doc_type, full_text, text_source, ocr_results)

    # 5. Image quality checks (FFT + edge — but NOT the aggressive ELA forgery detector)
    fft_score: float | None = None
    edge_score: float | None = None
    fft_flags: list[str] = []
    edge_flags: list[str] = []

    if image is not None:
        try:
            fft_score, fft_flags = fft_anomaly_score(image)
        except Exception:
            pass
        try:
            edge_score, edge_flags = edge_inconsistency_score(image)
        except Exception:
            pass

    # 6. Confidence scoring
    breakdown = build_score_breakdown(ocr_results, fields, doc_type, validation_score, fft_score, edge_score)
    rule_score = breakdown["overall"]

    # ── Blend Gemini AI confidence with rule-based score ──────────────────
    # If Gemini ran: 65% Gemini AI confidence + 35% rule-based
    # If Gemini failed: 100% rule-based
    if gemini_result and gemini_result.used_gemini:
        gemini_contrib = gemini_result.ai_confidence * 0.70
        rule_contrib = rule_score * 0.30
        final_score = round(gemini_contrib + rule_contrib, 1)
    else:
        final_score = rule_score

    # Apply forgery penalty (Gemini-based, more accurate)
    if gemini_forgery_score > 35:
        penalty = min((gemini_forgery_score - 35) * 0.5, 35)  # max -35pts
        final_score = max(0.0, round(final_score - penalty, 1))

    breakdown["overall"] = final_score

    # 7. PII masking
    masked_path = None
    masked_b64 = None
    if image is not None and doc_type in ("aadhaar", "pan") and ocr_results:
        try:
            masked = mask_pii_on_image(image, ocr_results, doc_type)
            masked_path = save_masked_image(masked, MASKED_OUTPUT / f"{doc_id}_masked.jpg")
            masked_b64 = _image_to_base64(masked)
        except Exception:
            logger.warning("PII masking failed for %s", doc_id)

    # 8. Combine flags
    all_flags = list(dict.fromkeys(validation_flags + gemini_flags + fft_flags + edge_flags))
    if avg_conf < 0.4 and "LOW_OCR_CONFIDENCE" not in all_flags:
        all_flags.append("LOW_OCR_CONFIDENCE")

    # 9. Decision
    status = decide_status(final_score, all_flags)

    # 10. Clean for display
    display_fields = _clean_fields_for_display(fields, doc_type)

    return {
        "confidence_score": final_score,
        "score_breakdown": breakdown,
        "flags": all_flags,
        "extracted_fields": display_fields,
        "full_text": full_text,
        "status": status,
        "text_source": text_source,
        "masked_image_path": masked_path,
        "ocr_confidence": round(avg_conf, 3),
        "original_path": original_path,
        "image_base64": image_b64,
        "masked_image_base64": masked_b64,
        "forgery_score": round(gemini_forgery_score, 1),
        "forgery_reason": gemini_result.forgery_reason if gemini_result and gemini_result.used_gemini else "",
        "ai_confidence": gemini_result.ai_confidence if gemini_result and gemini_result.used_gemini else None,
        "ai_powered": bool(gemini_result and gemini_result.used_gemini),
        "gemini_model": gemini_result.gemini_model if gemini_result else None,
        "gemini_raw_json": gemini_result.raw_json if gemini_result else None,
        "gemini_key_index": gemini_result.key_index if gemini_result else None,
    }


def doc_to_db_json(result: dict) -> dict:
    """Convert analysis result to DB-storable format."""
    return {
        "confidence_score": result["confidence_score"],
        "status": result["status"],
        "flags_json": json.dumps(result["flags"]),
        "fields_json": json.dumps(result["extracted_fields"], default=str),
        "text_source": result.get("text_source"),
        "masked_image_path": result.get("masked_image_path"),
        "full_text": result.get("full_text", ""),
        "score_breakdown_json": json.dumps(result.get("score_breakdown", {})),
        "ocr_confidence": result.get("ocr_confidence"),
        "image_base64": result.get("image_base64"),
        "masked_image_base64": result.get("masked_image_base64"),
        "gemini_model": result.get("gemini_model"),
        "gemini_raw_json": result.get("gemini_raw_json"),
        "forgery_score": result.get("forgery_score"),
        "forgery_reason": result.get("forgery_reason"),
        "ai_confidence": result.get("ai_confidence"),
        "ai_powered": result.get("ai_powered", False),
        "gemini_key_index": result.get("gemini_key_index"),
    }

