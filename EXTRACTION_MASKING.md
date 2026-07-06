# Extraction & Masking Guide

## Aadhaar (YOLO-primary)
| Class | Action |
|-------|--------|
| aadharNumber | Mask immediately — never OCR |
| address | Mask immediately — never OCR |
| name, dob, gender, city, state, pincode | RapidOCR on crop |

**Required YOLO classes:** name, dob, aadharNumber  
**Conf threshold:** 0.55

## PAN (YOLO-primary)
| Class | Action |
|-------|--------|
| pannumber, panno | Mask + OCR for regex validation only |

**Conf threshold:** 0.75  
**Regex:** `[A-Z]{5}\d{4}[A-Z]`

## Caste (text-layer)
1. PDF → PyMuPDF native text
2. DOCX → python-docx
3. Scan → RapidOCR fallback
4. Regex: caste category, cert number, authority, date

## Experience (text-layer)
1. Same extraction as caste
2. Regex: email, phone, company, employee, dates
3. Redact Aadhaar-like sequences in output

## Masking
- Black rectangles on PII regions (matches AI_mask test scripts)
- Masked images saved to `backend/masked_output/`
