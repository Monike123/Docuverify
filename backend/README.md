---
title: DocVerify AI - HR Document Verification
emoji: 🔍
colorFrom: green
colorTo: blue
sdk: docker
pinned: false
license: mit
app_port: 7860
---

# DocVerify AI — HR Document Verification & Extraction

AI-powered verification, extraction, and forgery detection for Indian HR documents.

**Supported Documents:** Aadhaar Card, PAN Card, Caste Certificate, Experience Letter, Education Certificate, Resume

## Features
- 🤖 **Gemini 3 Flash** vision analysis — 1000 free requests/day per key (5-key pool = ~5000/day)
- 🔒 **Forgery detection** — pixel-level manipulation analysis with calibrated scoring
- 📄 **Smart PDF handling** — renders pages to images before AI analysis
- 🗄️ **Full persistence** — all extractions + AI audit trail saved to Supabase
- 📱 **Mobile responsive** — works on phones and tablets

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health check |
| POST | `/upload` | Upload a document |
| POST | `/analyze/{doc_id}` | Run AI analysis |
| GET | `/status/{doc_id}` | Get result |
| GET | `/documents` | List all documents |
| GET | `/documents/stats` | Dashboard stats |

## Environment Variables (set in HF Space Secrets)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | Supabase PostgreSQL connection string |
| `GEMINI_API_KEYS` | ✅ | Comma-separated Gemini API keys |
| `GEMINI_MODEL` | ✅ | `gemini-3-flash` |
| `CORS_ORIGINS` | ✅ | Your Netlify URL (e.g. `https://docverify.netlify.app`) |
| `API_KEY` | Optional | Shared API key for demo security |
| `EASYOCR_GPU` | Optional | `false` (HF free spaces are CPU only) |

## Frontend

Deployed separately on Netlify — set `VITE_API_URL` to this Space's URL.
