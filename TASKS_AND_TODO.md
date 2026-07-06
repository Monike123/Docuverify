# Tasks & TODO — Execution Checklist

## Phase 1 — Foundation
- [x] FastAPI scaffold: main.py, config.py, models.py, requirements.txt
- [x] React/Vite frontend with routes
- [x] POST /upload with doc_type validation
- [x] model_registry.py YOLO singleton
- [x] Upload UI with 4 zones

## Phase 2 — YOLO Identity
- [x] Port preprocess.py, yolo_detect.py, mask.py from AI_mask
- [x] RapidOCR on non-PII crops
- [x] validators/aadhaar.py, validators/pan.py
- [x] fft_detect.py, edge_detect.py, confidence.py
- [x] POST /analyze, GET /masked
- [x] Result detail UI
- [x] E2E test a1.jpg + p1.jpg

## Phase 3 — Text Documents
- [x] text_extractor.py PyMuPDF/DOCX + OCR fallback
- [x] validators/caste.py, validators/experience.py
- [x] Caste + experience analyze flows

## Phase 4 — Verification + Dashboard
- [x] experience_service.py decision tree
- [x] company_scraper.py, SMTP/IMAP mailer
- [x] POST /verify-experience
- [x] Dashboard + HITL queue + manual review
- [x] gov_stubs/verify_stub.py
- [x] temp_uploads cleanup after analyze

## Phase 5 — Documentation
- [x] Updated PROJECT_OVERVIEW, TECH_STACK, INSTRUCTIONS, TASKS
- [x] EXTRACTION_MASKING.md
- [x] EXPERIENCE_VERIFICATION.md
- [x] GOV_API_STUBS.md

## Phase 6 — Accuracy Hardening
- [x] confidence.py: critical/warning flag gating, rebalanced weights, System Verified label
- [x] yolo_detect.py: dedupe, dual conf pass, upscale small images, path inference
- [x] ocr.py + preprocess.py: 15px padding, 120px min height, multi-pass OCR
- [x] validators tightened (aadhaar/pan/caste/experience), per-field confidence
- [x] pytest fixtures + tests/test_pipeline.py
- [x] scripts/benchmark.py for a1–a4 + p1
- [x] docx2txt dep, DEMO_MODE_EMAIL flag, fixtures/real/, Hindi OCR fallback
- [x] Result page: flag chips, field confidence table, Gov Verify, dashboard filters, drag-drop

## Phase 7 — Production Deployment & Showcase
- [x] YOLO weights served from Hugging Face Hub (config + model_registry + upload_weights.py)
- [x] Send-only Gmail SMTP; IMAP/Selenium gated behind flags; selenium moved to requirements-dev.txt
- [x] Security: env-locked CORS, upload size/magic-byte checks, rate limiting, security headers, sanitized errors, optional API key, hardened .gitignore
- [x] Render: Dockerfile (opencv-headless system libs, torch CPU), render.yaml with /data persistent disk
- [x] Frontend: landing + How-it-works pages, demo "Try a sample" mode, status legend, skeleton loader, polished design system
- [x] Netlify: netlify.toml (SPA redirect, build, headers), VITE_API_URL, production build verified
- [x] Docs: README, DEPLOYMENT.md, DEMO_SCRIPT.md
