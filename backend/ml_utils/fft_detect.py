import cv2
import numpy as np

from ml_utils.confidence import FFT_MAX


def fft_anomaly_score(image_bgr: np.ndarray) -> tuple[float, list[str]]:
    flags = []
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    block = 64
    variances = []

    for y in range(0, h - block, block):
        for x in range(0, w - block, block):
            patch = gray[y : y + block, x : x + block].astype(np.float32)
            f = np.fft.fft2(patch)
            fshift = np.fft.fftshift(f)
            magnitude = np.log(np.abs(fshift) + 1)
            variances.append(float(np.var(magnitude)))

    if len(variances) < 2:
        return FFT_MAX * 0.5, flags

    mean_v = np.mean(variances)
    std_v = np.std(variances)
    cv = std_v / (mean_v + 1e-6)

    if cv > 0.45:
        flags.append("FFT_ANOMALY_HIGH")
        score = max(5.0, FFT_MAX - (cv - 0.45) * 45)
    elif cv > 0.25:
        score = FFT_MAX - (cv - 0.25) * 37.5
    else:
        score = (FFT_MAX - 5.0) + (0.25 - cv) * 15

    return float(np.clip(score, 0, FFT_MAX)), flags
