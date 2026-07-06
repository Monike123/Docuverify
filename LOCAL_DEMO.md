# Local Demo Guide

Run DocVerify on your machine before deploying to Netlify + Hugging Face Spaces.

## Prerequisites

- Python 3.11+
- Node.js 20+
- Gemini API key(s) in environment (see below)

## 1. Backend

```powershell
cd docverify\backend
py -3 -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`:

- `GEMINI_API_KEYS` — one or more keys from [Google AI Studio](https://aistudio.google.com/apikey)
- `DATABASE_URL` — leave default for local SQLite, or set Supabase URL for cloud DB

Start the API:

```powershell
.\.venv\Scripts\uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

First analyze request may take 30–60s while EasyOCR models load.

Health check: http://127.0.0.1:8000/health  
API docs: http://127.0.0.1:8000/docs

## 2. Frontend

In a second terminal:

```powershell
cd docverify\frontend
npm install
npm run dev
```

Open http://localhost:5173

Default login: any demo user on the login page (local auth only).

## 3. Test with sample documents

Use files in `docverify/test_documents/`:

| File | Route |
| --- | --- |
| `aadhaar_1.jpg` | Upload → Aadhaar |
| `pan_1.jpg` | Upload → PAN |
| `caste_certificate.pdf` | Upload → Caste Certificate |
| `experience_letter.pdf` | Upload → Experience |
| `education_sample.pdf` | Upload → Education |

**Accepted formats:** JPG, JPEG, PNG, PDF only.

## 4. What to verify

- Result page shows **AI Powered** badge when Gemini is configured
- Forgery score and confidence breakdown appear
- Dashboard stats update after uploads
- Review queue lists low-confidence documents
- Mobile: resize browser or use phone — hamburger menu + bottom nav

## 5. Run tests

```powershell
cd docverify\backend
.\.venv\Scripts\pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest tests\ -v
```

## Troubleshooting

| Issue | Fix |
| --- | --- |
| `GEMINI_DISABLED` / no AI badge | Set `GEMINI_API_KEYS` in `.env` and restart backend |
| CORS error | Add `http://localhost:5173` to `CORS_ORIGINS` |
| Slow first request | EasyOCR cold start — wait up to 60s |
| 429 from Gemini | Add more keys to `GEMINI_API_KEYS` (comma-separated) |

See [DEPLOYMENT.md](DEPLOYMENT.md) for free-tier production deploy (Netlify + HF Space + Supabase).
