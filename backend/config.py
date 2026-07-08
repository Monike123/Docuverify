import json
import os
import time
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
WORKSPACE_ROOT = PROJECT_ROOT.parent

RAW_DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'docverify.db'}")
DATABASE_URL = RAW_DATABASE_URL
TEMP_UPLOADS = Path(os.getenv("TEMP_UPLOADS", BASE_DIR / "temp_uploads"))
MASKED_OUTPUT = Path(os.getenv("MASKED_OUTPUT", BASE_DIR / "masked_output"))
ORIGINAL_UPLOADS = Path(os.getenv("ORIGINAL_UPLOADS", BASE_DIR / "original_uploads"))


def _debug_log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    try:
        payload = {
            "sessionId": "8197a1",
            "runId": "startup-db-url",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with (WORKSPACE_ROOT / "debug-8197a1.log").open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, separators=(",", ":")) + "\n")
    except Exception:
        pass


# #region agent log
try:
    _split = urlsplit(DATABASE_URL)
    _userinfo = _split.netloc.rsplit("@", 1)[0] if "@" in _split.netloc else ""
    _debug_log(
        "H1-H4",
        "config.py:18",
        "database_url_loaded",
        {
            "scheme": _split.scheme,
            "hostname": _split.hostname,
            "port": _split.port,
            "username": _split.username,
            "netloc_at_count": _split.netloc.count("@"),
            "userinfo_has_brackets": "[" in _userinfo or "]" in _userinfo,
            "userinfo_has_raw_at": "@" in _userinfo,
            "is_sqlite": DATABASE_URL.startswith("sqlite"),
        },
    )
except Exception as exc:
    _debug_log(
        "H1-H4",
        "config.py:18",
        "database_url_parse_failed",
        {"error_type": type(exc).__name__},
    )
# #endregion

# --- EasyOCR Configuration ---
EASYOCR_LANGUAGES = ["en"]
EASYOCR_GPU = os.getenv("EASYOCR_GPU", "false").strip().lower() in ("1", "true", "yes")
EASYOCR_MODEL_DIR = Path(os.getenv("EASYOCR_MODEL_DIR", BASE_DIR / "ocr_models"))

# OCR tuning
OCR_TEXT_THRESHOLD = float(os.getenv("OCR_TEXT_THRESHOLD", "0.6"))
OCR_LINK_THRESHOLD = float(os.getenv("OCR_LINK_THRESHOLD", "0.3"))
OCR_LOW_TEXT = float(os.getenv("OCR_LOW_TEXT", "0.3"))
OCR_CANVAS_SIZE = int(os.getenv("OCR_CANVAS_SIZE", "2560"))
OCR_MAG_RATIO = float(os.getenv("OCR_MAG_RATIO", "2.0"))
OCR_LOW_CONFIDENCE_THRESHOLD = float(os.getenv("OCR_LOW_CONFIDENCE_THRESHOLD", "0.4"))

CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]

ACCEPTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}

ACCEPTED_EXTENSIONS: dict[str, set[str]] = {
    doc_type: set(ACCEPTED_IMAGE_EXTENSIONS)
    for doc_type in ("aadhaar", "pan", "caste", "experience", "education", "resume", "general")
}

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
IMAP_HOST = os.getenv("IMAP_HOST", "")
IMAP_USER = os.getenv("IMAP_USER", "")
IMAP_PASS = os.getenv("IMAP_PASS", "")
MOCK_REPLY = os.getenv("MOCK_REPLY", "")


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


# Send-only is the production default: send the verification email and stop.
# IMAP reply polling and the Selenium scraper are heavy / extra attack surface
# and stay off unless explicitly enabled.
ENABLE_REPLY_POLLING = _flag("ENABLE_REPLY_POLLING")
ENABLE_SCRAPER = _flag("ENABLE_SCRAPER")

# Upload + security knobs.
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
PDF_MAX_PAGES = int(os.getenv("PDF_MAX_PAGES", "3"))
GEMINI_PDF_PAGES = int(os.getenv("GEMINI_PDF_PAGES", "1"))
MAX_IMAGE_DIMENSION = int(os.getenv("MAX_IMAGE_DIMENSION", "2048"))
GEMINI_MAX_IMAGE_DIMENSION = int(os.getenv("GEMINI_MAX_IMAGE_DIMENSION", "768"))
API_KEY = os.getenv("API_KEY", "")

FREE_EMAIL_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "rediffmail.com"}

# ── Gemini Vision AI ─────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Comma-separated failover key pool (primary key always prepended)
GEMINI_API_KEYS = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]
# gemini-3-flash: 1000 RPD free, 1M context, agentic vision on images
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash")
GEMINI_ENABLED = bool(GEMINI_API_KEY or GEMINI_API_KEYS)
# Image sent to Gemini: max dimension (higher = better accuracy, more tokens)
GEMINI_MAX_IMAGE_DIMENSION = int(os.getenv("GEMINI_MAX_IMAGE_DIMENSION", "1024"))
# PDF rendering DPI for Gemini image conversion
GEMINI_PDF_DPI = int(os.getenv("GEMINI_PDF_DPI", "150"))
