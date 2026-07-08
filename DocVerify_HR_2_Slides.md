# DocVerify AI — 2-Slide Presentation (Government HR)

**Audience:** HR officer, government department, non-technical  
**Purpose:** Explain what DocVerify does, how it works, and why it is useful for official document checks  
**Duration:** ~5–7 minutes  
**Deck file:** `DocVerify_HR_Presentation.pptx` (diagrams built in — no external images)

---

## SLIDE 1 — DocVerify AI

**Header:** Government HR Document Verification

### Left column — Purpose for HR
- HR receives official papers: Aadhaar, PAN, caste, experience, education, resume.
- Manual checking is slow and risks errors or sharing private numbers.
- DocVerify uploads a photo/PDF and returns verified, review, or flagged.
- Sensitive data is masked; every result is saved for audit.

### Right column — Verification flow (diagram)
Upload → OCR Read → AI Check → Score → Secure Save

### Footer table — Supported documents

| Document type | What HR receives |
|---------------|------------------|
| Aadhaar | Number read, format checked, masked copy |
| PAN | PAN validated, name extracted |
| Caste certificate | Category and certificate details |
| Experience letter | Company, employee, dates |
| Education | Institute, degree, year |
| Resume | Contact, education, experience |

### Speaker notes
> “DocVerify is a digital assistant for the HR desk. You upload an official document. The system reads it, checks completeness and consistency, and gives a confidence score. Uncertain cases go to a review queue. HR keeps final authority.”

---

## SLIDE 2 — How DocVerify Works

**Header:** System overview for HR officers

### Top — System architecture (diagram)
**Netlify (HR website)** → **HF Space (Processing engine)** → **Supabase (Secure database)**

### Bottom left — Process and outcomes
1. HR uploads document on the website.
2. Processing engine reads text and runs AI + rule checks.
3. Results stored in secure database with scores and flags.
4. Final score: 70% AI analysis + 30% rule validation.

**Outcomes:** Verified · Manual Review · Rejected

### Bottom right — Example trust score chart

| Check | Example score |
|-------|----------------|
| OCR | 28 |
| Fields | 24 |
| Rules | 18 |
| Image | 12 |
| Final | 82 |

### Footer (bold)
**Upload → Check → Mask private data → Save → HR reviews if needed**

### Speaker notes
> “You only use the website. Processing runs on secure cloud services, and results are stored in a proper database. Technology handles first-level reading; officers decide on flagged cases.”

---

## Regenerate the PowerPoint

```powershell
cd docverify\backend
.\.venv\Scripts\python.exe ..\scripts\make_hr_ppt.py
```

Output: `docverify\DocVerify_HR_Presentation.pptx`
