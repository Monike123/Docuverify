"""Pipeline tests for the EasyOCR + Gemini document service."""

import json
import types
from pathlib import Path

import pytest

from ml_utils.confidence import build_score_breakdown, decide_status
from services.experience_service import verify_experience

BACKEND = Path(__file__).resolve().parent.parent
TEST_DOCS = BACKEND.parent / "test_documents"
FIXTURES = Path(__file__).parent / "fixtures"


class TestDecisionEngine:
    def test_critical_flag_rejects(self):
        status = decide_status(95.0, ["VERHOEFF_CHECKSUM_FAILED"])
        assert status == "Rejected"

    def test_high_score_verified(self):
        status = decide_status(92.0, [])
        assert status == "Auto-Verified"

    def test_score_breakdown_caps_at_100(self):
        breakdown = build_score_breakdown([], {"name": "x", "pan_number": "y"}, "pan", 20.0, 8.0, 7.0)
        assert breakdown["overall"] <= 100.0
        assert "ocr_quality" in breakdown


class TestCastePdf:
    def test_caste_sample_pdf_text(self):
        from ml_utils.text_extractor import extract_plain_text

        path = TEST_DOCS / "caste_certificate.pdf"
        if not path.exists():
            path = FIXTURES / "caste_sample.pdf"
        if not path.exists():
            pytest.skip("caste PDF fixture missing")
        text, source = extract_plain_text(str(path))
        assert source == "native"
        assert "CASTE" in text.upper()


class TestExperience:
    def test_experience_pdf_with_email_text(self):
        from ml_utils.text_extractor import extract_plain_text

        path = TEST_DOCS / "experience_letter.pdf"
        if not path.exists():
            pytest.skip("experience_letter.pdf missing")
        text, _ = extract_plain_text(str(path))
        assert "TechNova" in text or "EXPERIENCE" in text.upper()
        assert "@" in text

    def test_experience_pdf_no_email_text(self):
        from ml_utils.text_extractor import extract_plain_text

        path = TEST_DOCS / "experience_letter_no_email.pdf"
        if not path.exists():
            pytest.skip("experience_letter_no_email.pdf missing")
        text, _ = extract_plain_text(str(path))
        assert "@" not in text

    def test_experience_demo_mode_email(self):
        doc = types.SimpleNamespace(
            extracted_fields=json.dumps({"hr_email": "hr@acme.com", "company_name": "Acme", "employee_name": "John"}),
            flags=json.dumps([]),
        )
        outcome = verify_experience(doc)
        assert outcome.get("demo_mode") is True
        assert "DEMO_MODE_EMAIL" in outcome["flags"]


class TestUploadConfig:
    def test_only_image_extensions_accepted(self):
        from config import ACCEPTED_EXTENSIONS

        for doc_type, exts in ACCEPTED_EXTENSIONS.items():
            assert exts == {".jpg", ".jpeg", ".png", ".pdf"}, doc_type
