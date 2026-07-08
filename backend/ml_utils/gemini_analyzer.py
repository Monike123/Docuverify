"""Gemini Vision AI analyzer — token-efficient JSON-only document verification.

Key design decisions:
- gemini-3-flash: 1M context, 1000 RPD free, agentic vision at high media_resolution
- Single API call returns fields + forgery score + ai_confidence
- PDFs rendered to PNG image before analysis (never raw PDF bytes)
- max_output_tokens=400: covers full JSON output with room to spare
- response_mime_type='application/json' forces valid JSON output
- All keys rotate via call_with_failover (5-key pool = ~5000 req/day free)
"""

from __future__ import annotations

import io
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

from ml_utils.gemini_key_pool import call_with_failover
from ml_utils.gemini_prompts import build_prompt

logger = logging.getLogger("docverify.gemini")


@dataclass
class GeminiResult:
    fields: dict = field(default_factory=dict)
    forgery_score: float = 0.0
    forgery_reason: str = ""
    ai_confidence: float = 0.0
    ai_confidence_reason: str = ""
    is_suspicious: bool = False
    used_gemini: bool = False
    error: Optional[str] = None
    raw_json: Optional[str] = None
    gemini_model: Optional[str] = None
    key_index: Optional[int] = None


def _prepare_image(image_bgr: np.ndarray, max_dim: int = 1024) -> np.ndarray:
    """Resize image preserving aspect ratio. gemini-3-flash handles up to 3072px
    but 1024px is optimal for token efficiency at high_res mode."""
    h, w = image_bgr.shape[:2]
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        image_bgr = cv2.resize(
            image_bgr, (int(w * scale), int(h * scale)),
            interpolation=cv2.INTER_LANCZOS4
        )
    return image_bgr


def _parse_gemini_response(text: str) -> dict:
    """Extract JSON from Gemini response, stripping any accidental markdown."""
    text = text.strip()
    # Strip markdown code fences if model added them despite instructions
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    # Find the outermost JSON object
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return json.loads(m.group(0))
    raise ValueError(f"No JSON found in Gemini response: {text[:300]}")


def _call_gemini_api(api_key: str, pil_img, prompt: str, model_name: str) -> str:
    """Make a single Gemini API call. Raises on error (key pool handles retries)."""
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    # Disable all safety filters — HR documents can contain personal info
    safety = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    gen_cfg = genai.GenerationConfig(
        temperature=0.0,          # deterministic — we want consistent extraction
        max_output_tokens=400,    # ~300 tokens of JSON + buffer; saves quota
        response_mime_type="application/json",  # forces valid JSON, no prose
    )

    response = model.generate_content(
        [prompt, pil_img],
        safety_settings=safety,
        generation_config=gen_cfg,
    )
    return response.text


def analyze_with_gemini(
    image_bgr: np.ndarray,
    doc_type: str,
    pdf_text: Optional[str] = None,
) -> GeminiResult:
    """Analyze a document image with Gemini Vision.

    Args:
        image_bgr: OpenCV BGR image (already rendered if from PDF)
        doc_type: one of aadhaar|pan|caste|experience|education|resume|general
        pdf_text: optional PDF text layer for extra context (truncated to 300 chars)

    Returns GeminiResult with fields, forgery assessment, and confidence.
    Falls back gracefully if Gemini is unavailable.
    """
    from config import GEMINI_ENABLED, GEMINI_MODEL, GEMINI_MAX_IMAGE_DIMENSION
    from ml_utils.gemini_key_pool import get_api_keys

    if not GEMINI_ENABLED or not get_api_keys():
        return GeminiResult(error="Gemini not configured — set GEMINI_API_KEY")

    if image_bgr is None or image_bgr.size == 0:
        return GeminiResult(error="No image provided to Gemini")

    try:
        import PIL.Image

        # Prepare: resize to max dimension, convert to PIL for Gemini SDK
        max_dim = GEMINI_MAX_IMAGE_DIMENSION or 1024
        img_resized = _prepare_image(image_bgr, max_dim=max_dim)
        _, buf = cv2.imencode(".jpg", img_resized, [cv2.IMWRITE_JPEG_QUALITY, 88])
        pil_img = PIL.Image.open(io.BytesIO(buf.tobytes()))

        # Build the hyper-granular prompt
        prompt = build_prompt(doc_type)

        # Prepend PDF text hint if available (uses ~50 tokens, saves analysis errors)
        if pdf_text and len(pdf_text.strip()) > 20:
            # Only send first 300 chars — enough context without wasting tokens
            hint = pdf_text[:300].replace("\n", " ").strip()
            prompt = f"[PDF_TEXT_HINT: {hint}]\n\n{prompt}"

        # Call with key-pool failover (5 keys = ~5000 free requests/day)
        raw_text, key_index, err = call_with_failover(
            lambda key: _call_gemini_api(key, pil_img, prompt, GEMINI_MODEL)
        )

        if err or not raw_text:
            return GeminiResult(
                error=str(err or "Gemini call failed — all keys exhausted"),
                used_gemini=False
            )

        logger.info("Gemini[key=%s model=%s] raw: %.200s", key_index, GEMINI_MODEL, raw_text)

        # Parse the JSON response
        parsed = _parse_gemini_response(raw_text)

        # Extract fields — remove nulls, "null" strings, and empty values
        raw_fields = parsed.get("fields", {}) or {}
        fields = {
            k: v for k, v in raw_fields.items()
            if v is not None and str(v).strip() not in ("null", "", "None", "n/a", "N/A")
        }

        # Forgery assessment
        forgery_data = parsed.get("forgery", {}) or {}
        forgery_score = float(forgery_data.get("score", 0) or 0)
        forgery_reason = str(forgery_data.get("reason", "") or "")[:150]

        # AI extraction confidence
        conf_data = parsed.get("ai_confidence", {}) or {}
        ai_confidence = float(conf_data.get("score", 50) or 50)
        ai_confidence_reason = str(conf_data.get("reason", "") or "")[:150]

        # Conservative: only flag as suspicious when score exceeds threshold
        # Resumes never get forgery flags
        is_suspicious = (forgery_score > 35) and (doc_type != "resume")

        if is_suspicious:
            logger.info(
                "Gemini SUSPICIOUS doc_type=%s score=%.1f reason=%s",
                doc_type, forgery_score, forgery_reason
            )
        else:
            logger.info(
                "Gemini CLEAN doc_type=%s forgery=%.1f ai_conf=%.1f fields=%s",
                doc_type, forgery_score, ai_confidence, list(fields.keys())
            )

        return GeminiResult(
            fields=fields,
            forgery_score=round(forgery_score, 1),
            forgery_reason=forgery_reason,
            ai_confidence=round(ai_confidence, 1),
            ai_confidence_reason=ai_confidence_reason,
            is_suspicious=is_suspicious,
            used_gemini=True,
            raw_json=raw_text[:4000],  # store for DB, truncated to 4KB
            gemini_model=GEMINI_MODEL,
            key_index=key_index,
        )

    except Exception as exc:
        logger.warning("Gemini analysis failed: %s", exc, exc_info=True)
        return GeminiResult(error=str(exc), used_gemini=False)


def merge_fields(gemini_fields: dict, ocr_fields: dict, doc_type: str) -> dict:
    """Merge Gemini + OCR fields. Gemini wins on conflicts; OCR fills gaps.

    This is the 70/30 blend: Gemini is primary (visual AI), OCR is backup.
    """
    merged = dict(ocr_fields)  # start with OCR as base

    for key, value in gemini_fields.items():
        if value is not None and str(value).strip() not in ("null", "None", ""):
            merged[key] = value  # Gemini overrides OCR for this key

    # Aadhaar number: always use Gemini's privacy-safe display format
    if doc_type == "aadhaar" and "aadhaar_number" in gemini_fields:
        merged["aadhaar_number_display"] = gemini_fields["aadhaar_number"]
        merged.pop("aadhaar_number", None)      # never expose raw number
        merged.pop("aadhaar_number_raw", None)  # belt and suspenders

    return merged
