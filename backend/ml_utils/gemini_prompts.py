"""Per-document-type Gemini prompt schemas — JSON-only, minimal token output."""

# Explicit field keys per doc type (Gemini must only return these)
FIELD_SCHEMAS: dict[str, list[str]] = {
    "aadhaar": [
        "name", "date_of_birth", "gender", "aadhaar_number", "address", "pincode", "state",
    ],
    "pan": ["name", "father_name", "date_of_birth", "pan_number"],
    "caste": [
        "person_name", "category", "caste_name", "certificate_number",
        "issuing_authority", "issue_date", "state", "district",
    ],
    "experience": [
        "employee_name", "company_name", "designation", "joining_date",
        "relieving_date", "employment_duration", "hr_email",
    ],
    "education": [
        "institute_name", "student_name", "degree", "branch",
        "roll_number", "passing_year", "percentage_or_grade",
    ],
    "resume": [
        "candidate_name", "email", "phone", "skills",
        "experience_years", "current_company", "highest_qualification",
    ],
    "general": ["document_type", "key_info"],
}

_DOC_HINTS: dict[str, str] = {
    "aadhaar": "UIDAI Aadhaar. Genuine: UIDAI logo, 12-digit number, QR. Forgery: paste boundaries, font mismatch on number.",
    "pan": "Income Tax PAN. Genuine: Ashoka emblem, AAAAA9999A format. Forgery: wrong format, photo/text resolution mismatch.",
    "caste": "Govt caste certificate. Genuine: seal, authority name. Forgery: missing seal, font inconsistency.",
    "experience": "Company experience letter. Genuine: letterhead, dates, signature. Forgery: logo paste, date mismatch.",
    "education": "Degree/certificate. Genuine: university seal, roll no. Forgery: blurry seal, inserted marks.",
    "resume": "CV/resume. No forgery scoring needed — extract fields only.",
    "general": "Identify document type and extract visible key fields.",
}


def build_prompt(doc_type: str) -> str:
    keys = FIELD_SCHEMAS.get(doc_type, FIELD_SCHEMAS["general"])
    fields_json = ", ".join(f'"{k}":null' for k in keys)
    hint = _DOC_HINTS.get(doc_type, _DOC_HINTS["general"])
    forgery_rule = (
        'forgery:{"score":0-100,"reason":"max12words"}'
        if doc_type != "resume"
        else 'forgery:{"score":0,"reason":"n/a"}'
    )
    return (
        f"HR doc verifier. {hint}\n"
        f"Return ONLY valid JSON, no markdown:\n"
        f'{{"fields":{{{fields_json}}},'
        f'{forgery_rule},'
        f'"ai_confidence":{{"score":0-100,"reason":"max12words"}}}}\n'
        "Rules: forgery 0-15=genuine,16-35=quality issue,36-60=suspicious,61+=likely fake. "
        "ai_confidence=extraction certainty. "
        "aadhaar_number format XXXX XXXX last4 only. "
        "Missing=null. No extra keys. No prose."
    )
