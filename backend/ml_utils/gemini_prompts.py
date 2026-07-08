"""Per-document-type Gemini prompts — hyper-granular, zero-prose JSON output.

Design:
- Each doc type has visual layout, genuine markers, and specific forgery tells
- Output is STRICT JSON only — no markdown, no prose, no explanations
- max_output_tokens=400 covers all fields + forgery + confidence scores
- Field keys are fixed — Gemini must not invent new keys
- Forgery scoring is calibrated with real-world examples
"""

# ── Exact field keys per doc type ─────────────────────────────────────────
FIELD_SCHEMAS: dict[str, list[str]] = {
    "aadhaar": [
        "name", "date_of_birth", "gender",
        "aadhaar_number",   # output as XXXX XXXX last4 — never full 12
        "address", "pincode", "state",
    ],
    "pan": [
        "name", "father_name", "date_of_birth",
        "pan_number",       # format: AAAAA9999A (5 letters, 4 digits, 1 letter)
    ],
    "caste": [
        "person_name", "category",          # SC / ST / OBC / EWS / General
        "caste_name", "certificate_number",
        "issuing_authority", "issue_date",
        "state", "district",
    ],
    "experience": [
        "employee_name", "company_name", "designation",
        "joining_date", "relieving_date", "employment_duration",
        "hr_email",         # company email (used for verification)
    ],
    "education": [
        "institute_name", "student_name", "degree", "branch",
        "roll_number", "passing_year", "percentage_or_grade",
    ],
    "resume": [
        "candidate_name", "email", "phone",
        "skills",           # top 5, comma-separated
        "experience_years", "current_company", "highest_qualification",
    ],
    "general": ["document_type", "key_info"],
}

# ── Per-doc layout + forgery knowledge base ───────────────────────────────
_DOC_KNOWLEDGE: dict[str, str] = {

    "aadhaar": (
        "UIDAI Aadhaar Card issued by Government of India. "
        "LAYOUT: Blue/white gradient card. Top: UIDAI logo (left) + 'भारत सरकार / Government of India' (center). "
        "Body: holder photo (left), name, DOB, gender, address (right). Bottom: 12-digit Aadhaar number in groups of 4 (e.g. 1234 5678 9012). QR code bottom-right corner. "
        "GENUINE MARKERS: UIDAI text is embossed/crisp, font is uniform Noto Sans across all fields, QR matches the data, holographic strip visible in physical photos. "
        "FORGERY TELLS (be specific): (1) Aadhaar number region has different JPEG compression block boundaries than surrounding card — visible as slight blur or color banding around digits. "
        "(2) Name or DOB text has slightly different font weight/spacing compared to other text on same card. "
        "(3) Photo has different image quality/compression than the rest of the card. "
        "(4) Address text is typed in different font or has inconsistent line spacing. "
        "(5) Background gradient is interrupted or shows color seam near text fields. "
        "(6) QR code is missing, partially obscured, or clearly copy-pasted. "
        "IMPORTANT: Low image quality, watermarks, and lighting reflections are NOT forgery — score 5-15 for these."
    ),

    "pan": (
        "PAN Card issued by Income Tax Department, Government of India. "
        "LAYOUT: Cream/white background, blue header strip. Ashoka Lion Emblem top-left. "
        "'आयकर विभाग / Income Tax Department' and 'Govt. of India' in header. "
        "Holder photo right side. Name, Father's Name, DOB in center. PAN number bottom-center (format: AAAAA9999A). "
        "Signature strip at bottom. "
        "GENUINE MARKERS: PAN format exactly AAAAA9999A (5 caps, 4 digits, 1 cap), Ashoka emblem clear, holographic strip. "
        "FORGERY TELLS: (1) PAN number format wrong (e.g. all digits, wrong length). "
        "(2) Holder photo has different resolution/compression than card background. "
        "(3) Name/Father name area has cut-paste boundary (visible pixel seam). "
        "(4) Ashoka emblem is blurry while text around it is sharp. "
        "(5) Header text font differs from body text font. "
        "IMPORTANT: Printed PAN cards scanned at low DPI look grainy — that is NOT forgery."
    ),

    "caste": (
        "Indian State Government Caste/Community Certificate. "
        "LAYOUT: Official government letterhead with state emblem top-center. "
        "Certificate number top-right. Body: applicant name, parent name, caste, sub-caste, category (SC/ST/OBC/EWS/General), village/district. "
        "Bottom: Tehsildar/SDM/District Collector designation, official rubber stamp, handwritten signature, date. "
        "GENUINE MARKERS: Government rubber stamp impression (slightly blurry by nature), handwritten signature, official letterhead, unique certificate number. "
        "FORGERY TELLS: (1) Stamp is too perfect/sharp — real stamps are imperfect impressions. "
        "(2) Certificate number appears to be typed over different background. "
        "(3) Official title and date in different fonts. "
        "(4) Category field (SC/ST/OBC) appears added on top of existing text. "
        "IMPORTANT: Poor scan quality, skewed paper, and worn stamps on real documents score 0-15."
    ),

    "experience": (
        "Company Experience/Relieving Letter on official letterhead. "
        "LAYOUT: Company logo + name top. Date top-right. 'To Whom It May Concern' or addressee. "
        "Body: employee name, designation, joining date, relieving date, employment duration, sometimes CTC. "
        "Footer: HR Manager name, designation, company seal (optional), signature. "
        "GENUINE MARKERS: Consistent company letterhead throughout, professional language, company email/website footer. "
        "FORGERY TELLS: (1) Company logo appears at different DPI/compression than letterhead text. "
        "(2) Employee name or date appears in different font/size from surrounding text. "
        "(3) Joining/relieving dates are inconsistent (relieving before joining, future dates). "
        "(4) Signature or seal appears digitally inserted (uniform white box around it). "
        "(5) Company name in header differs from company name in body text. "
        "IMPORTANT: Digital PDFs with consistent fonts are likely genuine — score 0-15."
    ),

    "education": (
        "University/Board Degree Certificate or Marksheet. "
        "LAYOUT: University/Board name + seal top-center. Student photo (for degrees) or absent (marksheets). "
        "Enrollment/Roll number. Programme/Branch. Examination year/passing year. Marks/Grade/Percentage. "
        "Registrar/Controller signature + official seal bottom. "
        "GENUINE MARKERS: University seal is complex (hard to replicate cleanly), embossed or raised seal. "
        "FORGERY TELLS: (1) Percentage/grade appears in different font or color from surrounding marks. "
        "(2) University seal is blurry while surrounding text is sharp (opposite of genuine — real seals are slightly blurry). "
        "(3) Roll number or year has different background color (text was inserted). "
        "(4) Student name appears corrected or overwritten. "
        "IMPORTANT: Old paper documents scanned in poor quality are not forgeries — score 0-20."
    ),

    "resume": (
        "Resume/CV — user-created document, no forgery scoring needed. "
        "Extract key professional information only. "
        "IMPORTANT: Score forgery=0 always for resumes."
    ),

    "general": (
        "Unknown document type. First identify what kind of document this is, then extract all visible key-value information. "
        "Check if it appears to be an official government document or a private/company document."
    ),
}


def build_prompt(doc_type: str) -> str:
    """Build a hyper-granular, zero-prose prompt for this document type.

    Target token budget for RESPONSE: ~300 tokens max.
    The model must return ONLY valid JSON with no wrapping or prose.
    """
    keys = FIELD_SCHEMAS.get(doc_type, FIELD_SCHEMAS["general"])
    knowledge = _DOC_KNOWLEDGE.get(doc_type, _DOC_KNOWLEDGE["general"])

    # Build field template — null by default, Gemini fills in what it sees
    fields_template = "{" + ", ".join(f'"{k}": null' for k in keys) + "}"

    # Forgery section differs for resume (never forged)
    if doc_type == "resume":
        forgery_template = '{"score": 0, "reason": "n/a"}'
        forgery_rules = ""
    else:
        forgery_template = '{"score": 0-100, "reason": "max 15 words, specific evidence only"}'
        forgery_rules = (
            "FORGERY SCORE: 0-15=genuine document; 16-35=quality issues only (NOT forgery); "
            "36-60=suspicious (specific evidence required); 61-100=likely forged (clear evidence only). "
            "Only flag as forged if you see SPECIFIC visual evidence listed above. "
            "Low image quality, compression artifacts, and photo angle are NOT forgery. "
        )

    prompt = (
        f"You are a forensic HR document analyst. Analyze this image of an Indian {doc_type} document.\n"
        f"\n"
        f"DOCUMENT KNOWLEDGE:\n{knowledge}\n"
        f"\n"
        f"OUTPUT RULES (CRITICAL):\n"
        f"1. Return ONLY valid JSON — zero markdown, zero prose, zero explanation\n"
        f"2. Use EXACTLY these keys, no additions: {list(keys)}\n"
        f"3. For missing/unclear fields use null\n"
        f"4. aadhaar_number: output as 'XXXX XXXX <last4>' to protect privacy\n"
        f"5. pan_number: output full value (needed for format validation)\n"
        f"6. Dates: preserve exact format shown on document (e.g. '15/03/1990' or '15 Mar 1990')\n"
        f"\n"
        f"{forgery_rules}"
        f"ai_confidence = your certainty that extracted fields are correct (0=nothing readable, 100=all fields clear and certain).\n"
        f"\n"
        f"RETURN THIS EXACT JSON STRUCTURE (fill in values):\n"
        f'{{"fields": {fields_template}, '
        f'"forgery": {forgery_template}, '
        f'"ai_confidence": {{"score": 0-100, "reason": "max 10 words"}}}}'
    )
    return prompt
