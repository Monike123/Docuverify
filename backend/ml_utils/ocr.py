"""EasyOCR engine with multi-pass strategy."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from config import (
    EASYOCR_GPU,
    EASYOCR_LANGUAGES,
    EASYOCR_MODEL_DIR,
    OCR_CANVAS_SIZE,
    OCR_LINK_THRESHOLD,
    OCR_LOW_CONFIDENCE_THRESHOLD,
    OCR_LOW_TEXT,
    OCR_MAG_RATIO,
    OCR_TEXT_THRESHOLD,
)

logger = logging.getLogger("docverify.ocr")

_reader = None


# ── Data Model ──────────────────────────────────────────────────────────
@dataclass
class OcrResult:
    """Single text block detected by EasyOCR."""

    bbox: list[list[int]]  # 4-point polygon [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
    text: str
    confidence: float

    @property
    def rect(self) -> tuple[int, int, int, int]:
        """Axis-aligned bounding rectangle (x1, y1, x2, y2)."""
        xs = [p[0] for p in self.bbox]
        ys = [p[1] for p in self.bbox]
        return (min(xs), min(ys), max(xs), max(ys))

    @property
    def center_x(self) -> float:
        x1, _, x2, _ = self.rect
        return (x1 + x2) / 2

    @property
    def center_y(self) -> float:
        _, y1, _, y2 = self.rect
        return (y1 + y2) / 2

    @property
    def height(self) -> float:
        _, y1, _, y2 = self.rect
        return y2 - y1

    @property
    def width(self) -> float:
        x1, _, x2, _ = self.rect
        return x2 - x1


# ── Engine ──────────────────────────────────────────────────────────────
def get_ocr_reader():
    """Lazy singleton EasyOCR reader."""
    global _reader
    if _reader is None:
        import io
        import sys
        import easyocr

        # Fix Windows cp1252 crash from EasyOCR's █ progress bar character
        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

        EASYOCR_MODEL_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("Initializing EasyOCR with languages=%s, gpu=%s", EASYOCR_LANGUAGES, EASYOCR_GPU)
        _reader = easyocr.Reader(
            EASYOCR_LANGUAGES,
            gpu=EASYOCR_GPU,
            model_storage_directory=str(EASYOCR_MODEL_DIR),
            detect_network="craft",
        )
        logger.info("EasyOCR initialized successfully")
    return _reader



def ocr_fullpage(image: np.ndarray) -> list[OcrResult]:
    """Run EasyOCR on a single image, return structured results."""
    reader = get_ocr_reader()
    if reader is None or image is None or image.size == 0:
        return []

    try:
        raw = reader.readtext(
            image,
            detail=1,
            paragraph=False,
            text_threshold=OCR_TEXT_THRESHOLD,
            link_threshold=OCR_LINK_THRESHOLD,
            low_text=OCR_LOW_TEXT,
            canvas_size=OCR_CANVAS_SIZE,
            mag_ratio=OCR_MAG_RATIO,
            slope_ths=0.2,
            width_ths=0.7,
            contrast_ths=0.1,
        )
    except Exception as exc:
        logger.error("EasyOCR inference failed: %s", exc, exc_info=True)
        return []

    results: list[OcrResult] = []
    for entry in raw:
        bbox_raw, text, conf = entry
        # Convert bbox to list of int pairs
        bbox = [[int(round(p[0])), int(round(p[1]))] for p in bbox_raw]
        text = str(text).strip()
        if text:
            results.append(OcrResult(bbox=bbox, text=text, confidence=float(conf)))

    return results


def ocr_multipass(image: np.ndarray) -> list[OcrResult]:
    """Run OCR on multiple preprocessed variants, pick the best pass."""
    from ml_utils.preprocess import generate_ocr_variants

    variants = generate_ocr_variants(image)
    if not variants:
        return ocr_fullpage(image)

    best_results: list[OcrResult] = []
    best_score = -1.0

    for i, variant in enumerate(variants):
        try:
            results = ocr_fullpage(variant)
        except Exception as exc:
            logger.warning("OCR pass %d failed: %s", i, exc, exc_info=True)
            continue

        if not results:
            continue

        avg_conf = sum(r.confidence for r in results) / len(results)
        num_blocks = len(results)
        # Score: balance quality (confidence) with quantity (text blocks found)
        score = avg_conf * 0.6 + min(1.0, num_blocks / 30.0) * 0.4

        if score > best_score:
            best_score = score
            best_results = results

    return best_results if best_results else ocr_fullpage(image)


# ── Helpers ─────────────────────────────────────────────────────────────
def group_by_lines(results: list[OcrResult], tolerance_ratio: float = 0.5) -> list[list[OcrResult]]:
    """Group OCR results into logical reading lines by Y-proximity."""
    if not results:
        return []

    sorted_results = sorted(results, key=lambda r: (r.center_y, r.center_x))
    lines: list[list[OcrResult]] = []
    current_line: list[OcrResult] = [sorted_results[0]]

    for r in sorted_results[1:]:
        prev = current_line[-1]
        # If vertical distance is small relative to text height, same line
        avg_height = (prev.height + r.height) / 2
        tolerance = max(avg_height * tolerance_ratio, 10)
        if abs(r.center_y - prev.center_y) <= tolerance:
            current_line.append(r)
        else:
            current_line.sort(key=lambda x: x.center_x)
            lines.append(current_line)
            current_line = [r]

    if current_line:
        current_line.sort(key=lambda x: x.center_x)
        lines.append(current_line)

    return lines


def get_full_text(results: list[OcrResult]) -> str:
    """Concatenate all text in reading order."""
    lines = group_by_lines(results)
    return "\n".join(" ".join(r.text for r in line) for line in lines)


def get_average_confidence(results: list[OcrResult]) -> float:
    """Average OCR confidence across all blocks."""
    if not results:
        return 0.0
    return sum(r.confidence for r in results) / len(results)


def is_low_confidence(conf: float) -> bool:
    """Check if confidence is below threshold."""
    return conf < OCR_LOW_CONFIDENCE_THRESHOLD
