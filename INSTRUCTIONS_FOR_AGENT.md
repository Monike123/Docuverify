# Cursor Agent Instructions

## Rules
1. YOLO is primary for Aadhaar/PAN — never full-page OCR on ID cards
2. Never OCR or store raw `aadharNumber` — mask immediately
3. Native text first for PDF/DOCX (PyMuPDF, python-docx)
4. Graceful failure → `Manual Review Required`
5. Load YOLO models once at startup via `model_registry.py`

## Confidence Scoring
**Identity docs:** FFT (0–40) + Edge (0–30) + Field (0–30)  
**Experience:** Contact (0–50) + Format (0–30) + FFT (0–20)

## API Endpoints
- `POST /upload`, `POST /analyze/{doc_id}`, `GET /masked/{doc_id}`
- `GET /status/{doc_id}`, `GET /documents`, `GET /queue`
- `POST /verify-experience/{doc_id}`, `POST /manual-review/{doc_id}`
- `POST /gov-verify/{doc_id}`

## Start Order
1. Backend + model registry
2. YOLO pipeline + analyze
3. Frontend upload + result
4. Text extraction (caste/experience)
5. Experience verification + HITL dashboard
