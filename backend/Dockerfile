FROM python:3.11-slim

WORKDIR /app

# System deps for OpenCV, PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender1 poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY . .

# Create directories
RUN mkdir -p temp_uploads masked_output original_uploads ocr_models

# HF Spaces uses port 7860
EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
