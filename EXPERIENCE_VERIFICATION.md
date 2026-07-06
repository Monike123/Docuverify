# Experience Letter Verification

## Flow
1. Extract text (native PDF/DOCX preferred)
2. Parse email, company, employee, dates via regex
3. Decision tree:
   - HR email found → SMTP verification → IMAP poll
   - No email but company → Selenium lookup
   - Neither → Red Flag → HITL

## Red-Flag Codes
| Code | Meaning |
|------|---------|
| NO_EMAIL | No contact email in document |
| NO_COMPANY | Company not identified |
| FREE_EMAIL | gmail/yahoo only |
| EMAIL_BOUNCED | SMTP send failed |
| REPLY_DENIED | Company denied employment |
| NO_REPLY | Timeout waiting for reply |
| SCANNED_LOW_QUALITY | OCR fallback used |
| MISSING_DATES | No employment period |

## Demo Mode
Set `MOCK_REPLY=confirmed|denied|no_reply` in `.env` when SMTP not configured.

## SMTP (optional)
```
SMTP_HOST=sandbox.smtp.mailtrap.io
SMTP_PORT=587
SMTP_USER=...
SMTP_PASS=...
```

## Scoring
- Contact completeness: 50 pts (email 20, company 15, dates 15)
- Format validity: 30 pts (native text 15, keywords 15)
- FFT fraud: 20 pts max
