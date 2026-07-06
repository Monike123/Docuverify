# Tech Stack

## Frontend
- React + Vite + TypeScript
- React Router, Axios
- Custom CSS (dashboard styling)

## Backend
- Python FastAPI + Uvicorn
- SQLite + SQLAlchemy

## ML / Detection
- `ultralytics` YOLOv8 — Aadhaar/PAN field detection (from AI_mask)
- `rapidocr-onnxruntime` — crop OCR + scan fallback only
- `opencv-python` — FFT, edge analysis, masking
- `pymupdf` / `python-docx` — native PDF/DOCX text extraction

## Automation
- `smtplib` + `imaplib` — experience email verification
- `selenium` + `beautifulsoup4` — company contact lookup

## Folder Structure
```
docverify/
├── frontend/
├── backend/
│   ├── main.py
│   ├── ml_utils/
│   ├── services/
│   ├── scrapers/
│   ├── mailer/
│   └── gov_stubs/
└── temp_uploads/
```
