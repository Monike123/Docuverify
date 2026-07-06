# Test Documents

Ready-to-use sample files for trying DocVerify locally. Drag any of these into the matching
upload zone at http://localhost:5173/upload.

**Accepted formats:** JPG, JPEG, PNG, or PDF only.

| File | Upload as | What to expect |
| --- | --- | --- |
| `aadhaar_1.jpg` | Aadhaar | Aadhaar number detected + masked |
| `aadhaar_2.jpg` | Aadhaar | Second sample image |
| `aadhaar_3.jpg` | Aadhaar | Third sample image |
| `pan_1.jpg` | PAN | PAN field detected, OCR + format validation |
| `caste_certificate.pdf` | Caste Certificate | Native text extract; category + certificate number parsed |
| `experience_letter.pdf` | Experience Letter | Company + employee + HR email parsed |
| `experience_letter_no_email.pdf` | Experience Letter | Missing email → `NO_EMAIL` flag |
| `education_sample.pdf` | Education Certificate | Institution, degree, CGPA, registration number |

Notes:
- PDFs are processed as images (first page for Gemini; up to 3 pages for OCR text).
- With SMTP unset, experience verification runs in demo mode (no real email is sent).
- These are synthetic / sample documents for testing only.
