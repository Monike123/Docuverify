import cv2
import numpy as np

from ml_utils.confidence import EDGE_MAX


def edge_inconsistency_score(image_bgr: np.ndarray) -> tuple[float, list[str]]:
    flags = []
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    block = 48
    densities = []

    for y in range(0, h - block, block):
        for x in range(0, w - block, block):
            patch = gray[y : y + block, x : x + block]
            edges = cv2.Canny(patch, 50, 150)
            densities.append(float(np.mean(edges > 0)))

    if len(densities) < 2:
        return EDGE_MAX * 0.5, flags

    std_d = float(np.std(densities))
    if std_d > 0.12:
        flags.append("EDGE_INCONSISTENCY")
        score = max(5.0, EDGE_MAX - std_d * 100)
    else:
        score = (EDGE_MAX - 5.0) + (0.12 - std_d) * 33

    return float(np.clip(score, 0, EDGE_MAX)), flags
