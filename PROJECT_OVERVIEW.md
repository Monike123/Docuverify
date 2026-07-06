# DocVerify AI — Project Overview

## Goal
Prototype web app to verify 4 document types using YOLO field detection, lightweight OCR, text extraction, and automated experience verification.

## Documents
| # | Document | Detection | Verification |
|---|----------|-----------|--------------|
| 1 | Caste Certificate | Text-layer + regex | Confidence score + FFT |
| 2 | PAN Card | YOLO + crop OCR | Confidence score + FFT |
| 3 | Aadhaar Card | YOLO (8 classes) + crop OCR | Confidence score + FFT + mask PII |
| 4 | Experience Letter | Text-layer + regex | Email/Selenium + HITL |

## AI_mask Integration
- Aadhaar weights: `AI_mask/AI_mask/aadhar_masking/yolov8_mask_model10/weights/best.pt`
- PAN weights: `AI_mask/AI_mask/models/Pan_best.pt`
- Ported: `test_aadhar.py`, `test_pan.py`, `utlis.py` → `yolo_detect.py`, `mask.py`, `preprocess.py`

## Modules
1. **YOLO Fraud Detection** — field detect, mask, RapidOCR on crops, FFT/edge scoring
2. **Text Extraction** — PyMuPDF/python-docx native text for PDF/DOCX; RapidOCR fallback for scans
3. **Experience Verification** — regex contacts → SMTP/IMAP → HITL fallback
4. **Dashboard** — upload, review queue, manual override

## Success Criteria
- [x] Upload Aadhaar/PAN → YOLO detect + mask + confidence score
- [x] Upload Caste/Experience PDF/DOCX → text extract + regex
- [x] Red-flagged docs in HITL queue
- [x] Dashboard with color-coded scores
- [x] No raw Aadhaar/PAN stored in DB
