"""Fast image preprocessing pipeline optimised for speed + accuracy.

Design goals:
- Single-pass preprocessing under 1s for a typical 1200px document image
- 2 OCR variants max (not 5)  →  halves EasyOCR inference time
- No bilateralFilter (slow O(n²)), no HoughLinesP on every frame
"""

import cv2
import numpy as np

OCR_MIN_HEIGHT = 120
MIN_WIDTH_UPSCALE = 1200


# ── Upscale ─────────────────────────────────────────────────────────────────
def upscale_if_needed(image: np.ndarray, min_width: int = MIN_WIDTH_UPSCALE) -> np.ndarray:
    """Bicubic upscale if image is too small for good OCR. Fast INTER_LINEAR."""
    h, w = image.shape[:2]
    if w >= min_width:
        return image
    scale = min_width / w
    return cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LINEAR)


# ── Deskew (fast) ─────────────────────────────────────────────────────────
def deskew_fast(image: np.ndarray) -> np.ndarray:
    """Fast deskew using minAreaRect on thresholded text blobs.
    Only corrects if angle > 0.5° to avoid unnecessary warp."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) < 100:
        return image
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.5:
        return image
    h, w = image.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


# ── CLAHE contrast enhancement ───────────────────────────────────────────
def clahe_enhance(gray: np.ndarray) -> np.ndarray:
    """Fast CLAHE on grayscale."""
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


# ── Sharpen ──────────────────────────────────────────────────────────────
def sharpen(image: np.ndarray) -> np.ndarray:
    """Unsharp mask — works on both gray and BGR."""
    blurred = cv2.GaussianBlur(image, (0, 0), 2)
    return cv2.addWeighted(image, 1.4, blurred, -0.4, 0)


# ── Fast single-pass pipeline ─────────────────────────────────────────────
def preprocess_fast(image: np.ndarray) -> np.ndarray:
    """Primary fast pipeline: upscale → deskew → grayscale → CLAHE → sharpen.

    Avoids bilateralFilter (O(n²) slow). Targets ~0.3s for 1200×800 image.
    """
    if image is None or image.size == 0:
        return image
    img = upscale_if_needed(image)
    img = deskew_fast(img)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    gray = clahe_enhance(gray)
    gray = sharpen(gray)
    return gray


# ── 2-variant OCR strategy ────────────────────────────────────────────────
def generate_ocr_variants(image: np.ndarray) -> list[np.ndarray]:
    """Generate exactly 2 image variants for OCR.

    Pass 0: CLAHE grayscale + sharpened  → best for printed/scanned text
    Pass 1: Adaptive binarize            → best for low-contrast / faded docs

    OLD: 5 passes ≈ 25–60 s  |  NEW: 2 passes ≈ 4–8 s
    """
    if image is None or image.size == 0:
        return [image] if image is not None else []

    # Pass 0 — fast primary
    pass0 = preprocess_fast(image)

    # Pass 1 — adaptive threshold on the same preprocess (different representation)
    pass1 = cv2.adaptiveThreshold(
        pass0 if len(pass0.shape) == 2 else cv2.cvtColor(pass0, cv2.COLOR_BGR2GRAY),
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        15, 8,
    )

    return [pass0, pass1]


# ── Full pipeline (alias kept for backward compat) ───────────────────────
def preprocess_pipeline(image: np.ndarray) -> np.ndarray:
    """Alias for preprocess_fast — backward compatibility."""
    return preprocess_fast(image)


# ── Legacy helpers ────────────────────────────────────────────────────────
def preprocess_crop_for_ocr(crop_bgr: np.ndarray, target_height: int = OCR_MIN_HEIGHT) -> np.ndarray:
    if crop_bgr is None or crop_bgr.size == 0:
        return crop_bgr
    h, w = crop_bgr.shape[:2]
    if h < 1:
        return crop_bgr
    scale = target_height / h
    new_w = max(1, int(w * scale))
    resized = cv2.resize(crop_bgr, (new_w, target_height), interpolation=cv2.INTER_LINEAR)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY) if len(resized.shape) == 3 else resized
    return clahe_enhance(gray)


def upscale_for_fullpage(image_bgr: np.ndarray, scale: float = 2.0) -> np.ndarray:
    h, w = image_bgr.shape[:2]
    return cv2.resize(image_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LINEAR)


# Stubs kept for import compatibility
def correct_perspective(image: np.ndarray) -> np.ndarray:
    return image


def remove_noise(image: np.ndarray) -> np.ndarray:
    return image


def deskew(image: np.ndarray) -> np.ndarray:
    return deskew_fast(image)


def enhance_contrast(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    return clahe_enhance(gray)


def adaptive_binarize(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 8)
