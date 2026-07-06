"""Text extraction from image and PDF uploads (JPG, PNG, PDF only).

For images, uses EasyOCR via the ocr module.
For PDFs, renders up to PDF_MAX_PAGES at 150 DPI and runs OCR on page 1.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import fitz
import numpy as np

from config import MAX_IMAGE_DIMENSION, PDF_MAX_PAGES
from ml_utils.ocr import OcrResult, get_full_text, ocr_multipass

MIN_NATIVE_CHARS = 50
_PDF_DPI = 150


def _cap_image_dimension(img: np.ndarray, max_dim: int = MAX_IMAGE_DIMENSION) -> np.ndarray:
    h, w = img.shape[:2]
    longest = max(h, w)
    if longest <= max_dim:
        return img
    scale = max_dim / longest
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)


def extract_plain_text(file_path: str) -> tuple[str, str]:
    """Returns (text, source) where source is native|ocr|failed."""
    path = Path(file_path)
    ext = path.suffix.lower()

    try:
        if ext == ".pdf":
            return _extract_pdf(path)
        if ext in (".jpg", ".jpeg", ".png"):
            img = cv2.imread(str(path))
            if img is None:
                return "", "failed"
            img = _cap_image_dimension(img)
            return _ocr_image(img)
    except Exception:
        return "", "failed"

    return "", "failed"


def extract_with_ocr_results(file_path: str) -> tuple[str, str, list[OcrResult], np.ndarray | None]:
    """Extract text AND return OCR results + image for the full pipeline.

    Returns: (text, text_source, ocr_results, image_bgr_or_None)
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    try:
        if ext in (".jpg", ".jpeg", ".png"):
            img = cv2.imread(str(path))
            if img is None:
                return "", "failed", [], None
            img = _cap_image_dimension(img)
            results = ocr_multipass(img)
            text = get_full_text(results)
            return text, "ocr", results, img

        if ext == ".pdf":
            native_text = _get_pdf_text(path)
            img = _pdf_page_to_bgr(path, page=0)
            if img is not None:
                img = _cap_image_dimension(img)
            if len(native_text.strip()) >= MIN_NATIVE_CHARS:
                results = ocr_multipass(img) if img is not None else []
                return native_text, "native", results, img
            if img is not None:
                results = ocr_multipass(img)
                text = get_full_text(results)
                return text, "ocr", results, img
            return native_text, "native" if native_text.strip() else "failed", [], None

    except Exception:
        pass

    return "", "failed", [], None


def _ocr_image(img: np.ndarray) -> tuple[str, str]:
    """Run EasyOCR multipass on an image."""
    results = ocr_multipass(img)
    text = get_full_text(results)
    if text.strip():
        return text, "ocr"
    return "", "failed"


def _get_pdf_text(path: Path) -> str:
    """Get native text from first PDF_MAX_PAGES pages."""
    doc = fitz.open(str(path))
    text_parts: list[str] = []
    for page_num in range(min(len(doc), PDF_MAX_PAGES)):
        text_parts.append(doc.load_page(page_num).get_text())
    doc.close()
    return "\n".join(text_parts).strip()


def _extract_pdf(path: Path) -> tuple[str, str]:
    text = _get_pdf_text(path)
    if len(text) >= MIN_NATIVE_CHARS:
        return text, "native"
    img = _pdf_page_to_bgr(path, page=0)
    if img is not None:
        img = _cap_image_dimension(img)
        return _ocr_image(img)
    return text, "native" if text else "failed"


def pdf_to_image_bgr(file_path: str, page: int = 0) -> np.ndarray | None:
    return _pdf_page_to_bgr(Path(file_path), page)


def _pdf_page_to_bgr(path: Path, page: int = 0) -> np.ndarray | None:
    try:
        doc = fitz.open(str(path))
        if page >= len(doc):
            doc.close()
            return None
        zoom = _PDF_DPI / 72.0
        pix = doc.load_page(page).get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        doc.close()
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        elif pix.n == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        return img
    except Exception:
        return None
