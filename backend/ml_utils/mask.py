"""PII masking using OCR bounding boxes — no YOLO dependency."""

from pathlib import Path
import re

import cv2
import numpy as np
from PIL import Image, ImageDraw

from ml_utils.ocr import OcrResult

# Regex patterns for PII fields to mask
PII_PATTERNS: dict[str, list[re.Pattern]] = {
    "aadhaar": [
        re.compile(r"\d{4}\s?\d{4}\s?\d{4}"),   # Full Aadhaar number
    ],
    "pan": [
        re.compile(r"[A-Z]{5}\d{4}[A-Z]"),       # PAN number
    ],
}

# Additional keyword-based masking: if an OCR block near these labels,
# mask the VALUE block (the one to the right/below)
PII_LABELS: dict[str, list[str]] = {
    "aadhaar": ["address", "पता"],
    "pan": [],
}


def mask_pii_on_image(
    image_bgr: np.ndarray,
    ocr_results: list[OcrResult],
    doc_type: str,
) -> np.ndarray:
    """Mask PII fields on the image using OCR bounding boxes."""
    img_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    img_pil = Image.fromarray(img_rgb)
    draw = ImageDraw.Draw(img_pil)

    patterns = PII_PATTERNS.get(doc_type, [])

    for result in ocr_results:
        for pat in patterns:
            if pat.search(result.text):
                _draw_mask(draw, result.bbox, img_pil.size)
                break

    # Mask address region for Aadhaar (bottom-right blocks after "Address" label)
    if doc_type == "aadhaar":
        _mask_address_region(draw, ocr_results, img_pil.size)

    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def _draw_mask(draw: ImageDraw.ImageDraw, bbox: list[list[int]], img_size: tuple[int, int]):
    """Draw a black rectangle over a bounding box."""
    w, h = img_size
    xs = [max(0, min(p[0], w)) for p in bbox]
    ys = [max(0, min(p[1], h)) for p in bbox]
    x1, x2 = min(xs), max(xs)
    y1, y2 = min(ys), max(ys)
    # Add small padding
    pad = 3
    draw.rectangle([x1 - pad, y1 - pad, x2 + pad, y2 + pad], fill=(0, 0, 0))


def _mask_address_region(draw: ImageDraw.ImageDraw, results: list[OcrResult], img_size: tuple[int, int]):
    """Mask text blocks in the address region of an Aadhaar card."""
    # Find "Address" or "पता" label
    address_label = None
    for r in results:
        if any(kw in r.text.lower() for kw in ["address", "पता"]):
            address_label = r
            break

    if address_label is None:
        return

    # Mask all blocks below the address label (within reasonable distance)
    _, label_y1, _, label_y2 = address_label.rect
    img_h = img_size[1]
    max_y = label_y2 + (img_h - label_y2)  # everything below

    for r in results:
        _, ry1, _, _ = r.rect
        if ry1 >= label_y1 and r is not address_label:
            _draw_mask(draw, r.bbox, img_size)


def save_masked_image(image_bgr: np.ndarray, output_path: Path) -> str:
    """Save masked image to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), image_bgr)
    return str(output_path)
