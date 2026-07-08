FROM python:3.11-slim

# ── Labels required by HF Spaces ──────────────────────────────────────────
LABEL maintainer="Monike123"
LABEL description="DocVerify AI — HR Document Verification & Extraction"

WORKDIR /app

# ── System dependencies ────────────────────────────────────────────────────
# libgl1 + libglib2.0-0 → OpenCV
# poppler-utils          → pdf2image (PDF → PNG rendering)
# libgomp1               → EasyOCR threading
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libgomp1 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies (cached layer — only rebuilds on requirements change) ──
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── Application code ──────────────────────────────────────────────────────
COPY . .

# ── Runtime directories ────────────────────────────────────────────────────
RUN mkdir -p temp_uploads masked_output original_uploads ocr_models

# ── HF Spaces: port MUST be 7860 ──────────────────────────────────────────
EXPOSE 7860

# ── Start server ──────────────────────────────────────────────────────────
# Workers=1 keeps RAM under 8GB HF free limit (EasyOCR alone is ~1.5GB)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
