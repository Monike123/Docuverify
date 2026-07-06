# Demo Script (3 minutes)

A guided walkthrough to showcase DocVerify end-to-end. Use the **"Try a sample"** buttons so you
don't need your own documents.

## 0. Setup (10s)
- Open the live site (Netlify) or `http://localhost:5173`.
- Start on the landing page — point out the four document types and the privacy promise
  ("0 raw PII stored").

## 1. Aadhaar — detection + masking + gating (45s)
- Go to **Verify**, click **Try a sample** under *Aadhaar*.
- On the result page, highlight:
  - **Masked preview** — the Aadhaar number/address are blacked out.
  - **Per-field table** — YOLO and OCR confidences.
  - **Status** — typically `Pending` with `MISSING_YOLO_NAME` / `MISSING_YOLO_DOB` chips on the tiny
    sample image. Key talking point: a high fraud score alone can NOT produce "System Verified" —
    critical/warning flags gate the status.

## 2. PAN — OCR + format validation (30s)
- Back to **Verify**, **Try a sample** under *PAN*.
- Show `pan_validated: true` in the fields table and the validated status. Mention multi-pass OCR
  (CLAHE/OTSU/invert) that recovers the PAN string from a noisy crop.

## 3. Experience letter — extraction + email (45s)
- **Try a sample** under *Experience Letter*.
- Show extracted **company**, **employee**, and **HR email**.
- Click **Verify Employment**:
  - With Gmail SMTP configured → a real verification email is sent; status becomes
    `Pending Verification` (send-only: a human resolves the final decision).
  - Without SMTP → a "Demo mode" banner appears (no email sent).

## 4. Caste certificate — text extraction (20s)
- **Try a sample** under *Caste Certificate* (PDF).
- Show native text extraction (`text_source: native`), detected caste category and certificate
  number, and the score.

## 5. Dashboard + HITL review (30s)
- Open **Dashboard** — filter by status and document type.
- Open **HITL Review** — approve/reject a queued item; show the status update.

## 6. How it works (20s)
- Open **How it works** — pipeline steps, the two YOLO models, deployment topology, and the
  privacy-by-design section.

## Talking points to land
- **Privacy-first**: originals deleted post-analysis; raw Aadhaar/PAN never stored.
- **Trustworthy scoring**: flag-gated status prevents false "Verified".
- **Real ML, real infra**: YOLO + OCR + fraud signals, weights on HF Hub, API on Render, SPA on
  Netlify, live email.
- **Reproducible**: `pytest tests/` (10 passing) and `scripts/benchmark.py` as evidence.
