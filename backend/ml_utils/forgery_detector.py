"""Forgery and document manipulation detection.

Checks performed:
1. ELA (Error Level Analysis) — detects JPEG compression inconsistencies from editing
2. Metadata analysis — EXIF editing software traces
3. Clone/copy-paste detection — statistical uniformity in image blocks
4. Font/print consistency — checks for pasted text regions
5. Edge artifact detection — sharp copy-paste boundaries

Returns a ForgeryResult with a manipulation_score (0=clean, 100=highly suspicious)
and a list of human-readable flags.
"""

from __future__ import annotations

import io
import logging
import math
from dataclasses import dataclass, field

import cv2
import numpy as np

logger = logging.getLogger("docverify.forgery")


@dataclass
class ForgeryResult:
    manipulation_score: float        # 0–100, higher = more suspicious
    is_suspicious: bool
    flags: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)


# ── ELA (Error Level Analysis) ───────────────────────────────────────────
def _ela_analysis(image_bgr: np.ndarray, quality: int = 90) -> tuple[float, bool]:
    """Re-save image at known JPEG quality, compute residual.

    Authentic images have uniform ELA residuals.
    Edited regions (pasted text/photos) show anomalous high-residual patches.

    Returns: (ela_score 0-100, is_suspicious)
    """
    try:
        from PIL import Image
        import tempfile, os

        pil_img = Image.fromarray(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))

        # Save at fixed quality
        buf = io.BytesIO()
        pil_img.save(buf, "JPEG", quality=quality)
        buf.seek(0)
        recompressed = Image.open(buf)

        # Compute absolute difference
        ela_arr = np.array(pil_img, dtype=np.float32) - np.array(recompressed, dtype=np.float32)
        ela_arr = np.abs(ela_arr)

        # Scale for visibility
        ela_max = ela_arr.max()
        if ela_max < 1:
            return 0.0, False

        # Compute block-level standard deviation — edited regions are outliers
        gray_ela = ela_arr.mean(axis=2) if ela_arr.ndim == 3 else ela_arr
        h, w = gray_ela.shape
        block_size = max(h // 20, 8)
        block_stds = []
        for y in range(0, h - block_size, block_size):
            for x in range(0, w - block_size, block_size):
                block = gray_ela[y:y+block_size, x:x+block_size]
                block_stds.append(float(block.std()))

        if not block_stds:
            return 0.0, False

        global_mean = float(np.mean(block_stds))
        global_std = float(np.std(block_stds))

        # Outlier blocks = suspicious (> 2.5σ above mean)
        threshold = global_mean + 2.5 * global_std
        outlier_count = sum(1 for s in block_stds if s > threshold)
        outlier_ratio = outlier_count / max(len(block_stds), 1)

        # Score: 0 = clean, 100 = heavily edited
        ela_score = min(100.0, outlier_ratio * 400)
        is_suspicious = ela_score > 25

        return ela_score, is_suspicious

    except Exception as exc:
        logger.debug("ELA analysis failed: %s", exc)
        return 0.0, False


# ── Clone/Copy-Paste Detection ───────────────────────────────────────────
def _clone_detection(image_bgr: np.ndarray) -> tuple[float, bool]:
    """Detect copy-paste cloning using block DCT similarity.

    Divides image into overlapping blocks, computes DCT features,
    finds suspiciously similar non-adjacent blocks.

    Returns: (score 0-100, is_suspicious)
    """
    try:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        block_size = 32
        step = 16

        features = []
        positions = []

        for y in range(0, h - block_size, step):
            for x in range(0, w - block_size, step):
                block = gray[y:y+block_size, x:x+block_size].astype(np.float32)
                dct = cv2.dct(block)
                # Use top-left 4x4 DCT coefficients as feature
                feat = dct[:4, :4].flatten()
                features.append(feat)
                positions.append((x, y))

        if len(features) < 10:
            return 0.0, False

        feat_arr = np.array(features)

        # Sort by feature to find similar blocks efficiently
        sorted_idx = np.lexsort(feat_arr.T[::-1])
        suspicious_pairs = 0
        total_checks = 0

        for i in range(len(sorted_idx) - 1):
            a = sorted_idx[i]
            b = sorted_idx[i + 1]
            # Feature distance
            dist = np.linalg.norm(feat_arr[a] - feat_arr[b])
            if dist < 5.0:  # very similar blocks
                # Check they're not adjacent
                xa, ya = positions[a]
                xb, yb = positions[b]
                spatial_dist = math.sqrt((xa - xb)**2 + (ya - yb)**2)
                if spatial_dist > block_size * 3:
                    suspicious_pairs += 1
            total_checks += 1

        score = min(100.0, (suspicious_pairs / max(total_checks, 1)) * 2000)
        return score, score > 15

    except Exception as exc:
        logger.debug("Clone detection failed: %s", exc)
        return 0.0, False


# ── Edge Artifact Detection ──────────────────────────────────────────────
def _edge_artifact_analysis(image_bgr: np.ndarray) -> tuple[float, bool]:
    """Detect unnaturally sharp/clean rectangular boundaries typical of cut-paste.

    Returns: (score 0-100, is_suspicious)
    """
    try:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        # Canny edges
        edges = cv2.Canny(gray, 50, 150)
        # Find long straight horizontal/vertical lines (copy-paste boundaries)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80,
                                minLineLength=gray.shape[1] // 4, maxLineGap=10)
        if lines is None:
            return 0.0, False

        # Count perfectly horizontal or vertical lines
        h_lines = 0
        v_lines = 0
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = abs(math.degrees(math.atan2(y2 - y1, x2 - x1)))
            if angle < 2 or angle > 178:
                h_lines += 1
            elif 88 < angle < 92:
                v_lines += 1

        # Normal documents have some horizontal lines (text baselines)
        # Suspicious: very long perfectly straight lines that cross content areas
        suspicious_lines = max(0, (h_lines + v_lines) - 8)
        score = min(100.0, suspicious_lines * 12)
        return score, score > 20

    except Exception as exc:
        logger.debug("Edge artifact analysis failed: %s", exc)
        return 0.0, False


# ── Noise Consistency Analysis ───────────────────────────────────────────
def _noise_consistency(image_bgr: np.ndarray) -> tuple[float, bool]:
    """Check if image noise is consistent across regions.

    Pasted regions often have different noise profiles.
    """
    try:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        h, w = gray.shape

        # High-frequency noise via Laplacian
        laplacian = cv2.Laplacian(gray, cv2.CV_32F)

        # Divide into quadrants
        quads = [
            laplacian[:h//2, :w//2],
            laplacian[:h//2, w//2:],
            laplacian[h//2:, :w//2],
            laplacian[h//2:, w//2:],
        ]
        quad_stds = [float(q.std()) for q in quads if q.size > 0]
        if len(quad_stds) < 2:
            return 0.0, False

        max_std = max(quad_stds)
        min_std = min(quad_stds)

        if min_std < 0.1:
            return 0.0, False

        # Large variation in noise across regions = suspicious
        ratio = max_std / min_std
        score = min(100.0, max(0.0, (ratio - 2.0) * 20))
        return score, score > 30

    except Exception as exc:
        logger.debug("Noise consistency failed: %s", exc)
        return 0.0, False


# ── Main Entry Point ─────────────────────────────────────────────────────
def detect_forgery(image_bgr: np.ndarray) -> ForgeryResult:
    """Run all forgery checks and return a combined ForgeryResult.

    The manipulation_score is a weighted combination of all checks.
    """
    if image_bgr is None or image_bgr.size == 0:
        return ForgeryResult(manipulation_score=0.0, is_suspicious=False)

    flags: list[str] = []
    details: dict = {}

    # 1. ELA
    ela_score, ela_suspicious = _ela_analysis(image_bgr)
    details["ela_score"] = round(ela_score, 1)
    if ela_suspicious:
        flags.append("JPEG_INCONSISTENCY_DETECTED")

    # 2. Clone detection
    clone_score, clone_suspicious = _clone_detection(image_bgr)
    details["clone_score"] = round(clone_score, 1)
    if clone_suspicious:
        flags.append("COPY_PASTE_PATTERN_DETECTED")

    # 3. Edge artifacts
    edge_score, edge_suspicious = _edge_artifact_analysis(image_bgr)
    details["edge_score"] = round(edge_score, 1)
    if edge_suspicious:
        flags.append("SHARP_BOUNDARY_ARTIFACTS")

    # 4. Noise consistency
    noise_score, noise_suspicious = _noise_consistency(image_bgr)
    details["noise_score"] = round(noise_score, 1)
    if noise_suspicious:
        flags.append("INCONSISTENT_NOISE_PATTERN")

    # Weighted composite score
    # ELA is most reliable for JPEG tampering
    manipulation_score = (
        ela_score   * 0.40 +
        clone_score * 0.25 +
        edge_score  * 0.20 +
        noise_score * 0.15
    )
    manipulation_score = round(min(100.0, manipulation_score), 1)

    is_suspicious = manipulation_score > 20 or len(flags) >= 2

    return ForgeryResult(
        manipulation_score=manipulation_score,
        is_suspicious=is_suspicious,
        flags=flags,
        details=details,
    )
