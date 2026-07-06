"""Gemini Vision AI analyzer — token-efficient JSON-only document verification."""

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

GEMINI_MAX_IMAGE_DIM = 768
GEMINI_JPEG_QUALITY = 82


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


def _prepare_image(image_bgr: np.ndarray) -> np.ndarray:
    from config import GEMINI_MAX_IMAGE_DIMENSION

    h, w = image_bgr.shape[:2]
    max_dim = min(GEMINI_MAX_IMAGE_DIM, GEMINI_MAX_IMAGE_DIMENSION)
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        image_bgr = cv2.resize(image_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return image_bgr


def _parse_gemini_response(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return json.loads(m.group(0))
    raise ValueError(f"No JSON in response: {text[:200]}")


def _call_gemini_api(api_key: str, pil_img, prompt: str, model_name: str) -> str:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    safety = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    gen_cfg = genai.GenerationConfig(
        temperature=0.0,
        max_output_tokens=256,
        response_mime_type="application/json",
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
    from config import GEMINI_ENABLED, GEMINI_MODEL
    from ml_utils.gemini_key_pool import get_api_keys

    if not GEMINI_ENABLED or not get_api_keys():
        return GeminiResult(error="Gemini not configured")

    if image_bgr is None or image_bgr.size == 0:
        return GeminiResult(error="No image provided")

    try:
        import PIL.Image

        image_bgr = _prepare_image(image_bgr)
        _, buf = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, GEMINI_JPEG_QUALITY])
        pil_img = PIL.Image.open(io.BytesIO(buf.tobytes()))

        prompt = build_prompt(doc_type)
        if pdf_text and len(pdf_text) > 20:
            prompt = f"[pdf_hint:{pdf_text[:200].replace(chr(10), ' ')}]\n{prompt}"

        raw_text, key_index, err = call_with_failover(
            lambda key: _call_gemini_api(key, pil_img, prompt, GEMINI_MODEL)
        )

        if err or not raw_text:
            return GeminiResult(error=str(err or "Gemini call failed"), used_gemini=False)

        parsed = _parse_gemini_response(raw_text)
        fields = parsed.get("fields", {}) or {}
        fields = {k: v for k, v in fields.items() if v is not None and str(v) not in ("null", "", "None")}

        forgery = parsed.get("forgery", {}) or {}
        forgery_score = float(forgery.get("score", 0))
        forgery_reason = str(forgery.get("reason", ""))[:120]

        ai_conf = parsed.get("ai_confidence", {}) or {}
        ai_confidence_score = float(ai_conf.get("score", 50))
        ai_confidence_reason = str(ai_conf.get("reason", ""))[:120]

        is_suspicious = forgery_score > 35 and doc_type != "resume"

        return GeminiResult(
            fields=fields,
            forgery_score=round(forgery_score, 1),
            forgery_reason=forgery_reason,
            ai_confidence=round(ai_confidence_score, 1),
            ai_confidence_reason=ai_confidence_reason,
            is_suspicious=is_suspicious,
            used_gemini=True,
            raw_json=raw_text[:4000],
            gemini_model=GEMINI_MODEL,
            key_index=key_index,
        )

    except Exception as exc:
        logger.warning("Gemini analysis failed: %s", exc)
        return GeminiResult(error=str(exc), used_gemini=False)


def merge_fields(gemini_fields: dict, ocr_fields: dict, doc_type: str) -> dict:
    merged = dict(ocr_fields)
    for key, value in gemini_fields.items():
        if value and str(value).strip() and str(value) not in ("null", "None"):
            merged[key] = value
    if doc_type == "aadhaar" and "aadhaar_number" in gemini_fields:
        merged["aadhaar_number_display"] = gemini_fields["aadhaar_number"]
        merged.pop("aadhaar_number", None)
    return merged
