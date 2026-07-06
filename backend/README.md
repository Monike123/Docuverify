---
title: DocVerify API
emoji: 📄
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# DocVerify API

FastAPI backend for HR document verification: EasyOCR + Gemini 3 Flash + Supabase persistence.

## Secrets (Space Settings)

| Variable | Description |
| --- | --- |
| `DATABASE_URL` | Supabase PostgreSQL connection string |
| `GEMINI_API_KEYS` | Comma-separated Gemini API keys (failover) |
| `GEMINI_MODEL` | `gemini-3-flash` |
| `CORS_ORIGINS` | Netlify frontend URL |
| `API_KEY` | Optional demo protection |

See `DEPLOYMENT.md` in the parent repo for full deploy instructions.
