"""DocVerify AI — FastAPI entry point."""

import asyncio
import base64
import concurrent.futures
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from config import API_KEY, CORS_ORIGINS, MASKED_OUTPUT, ORIGINAL_UPLOADS, WORKSPACE_ROOT
from database import Base, engine, get_db
from gov_stubs.verify_stub import gov_verify_stub
from models import Document
from schemas import (
    AnalyzeResponse,
    GovVerifyResponse,
    ManualReviewRequest,
    StatsResponse,
    StatusResponse,
    UploadResponse,
    VerifyExperienceResponse,
)
from services.document_service import analyze_document, doc_to_db_json
from services.experience_service import verify_experience
from services.storage_service import ensure_dirs, get_upload_path, save_upload, validate_upload

logger = logging.getLogger("docverify")


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

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])

# Thread pool for CPU-bound OCR work (keeps event loop free)
_ocr_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="ocr")

app = FastAPI(title="DocVerify AI", version="2.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response


app.add_middleware(SecurityHeadersMiddleware)


def require_api_key(x_api_key: str | None = Header(default=None)):
    """Optional gate: when API_KEY is set, mutating endpoints require a matching header."""
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.on_event("startup")
def startup():
    # #region agent log
    _debug_log("H1-H4", "main.py:103", "startup_begin", {"step": "create_all"})
    # #endregion
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        # #region agent log
        _debug_log(
            "H1-H4",
            "main.py:107",
            "startup_create_all_failed",
            {"error_type": type(exc).__name__, "error_text": str(exc)[:240]},
        )
        # #endregion
        raise
    ensure_dirs()
    MASKED_OUTPUT.mkdir(parents=True, exist_ok=True)
    ORIGINAL_UPLOADS.mkdir(parents=True, exist_ok=True)
    # Pre-warm EasyOCR in background — model loads once, all requests stay fast
    threading.Thread(target=_prewarm_ocr, daemon=True, name="ocr-prewarm").start()


def _prewarm_ocr():
    """Load EasyOCR model at startup so the first upload request is instant."""
    try:
        import numpy as np
        from ml_utils.ocr import get_ocr_reader
        logger.info("Pre-warming EasyOCR...")
        reader = get_ocr_reader()
        # Dry-run on tiny blank image to fully JIT-compile model
        blank = (255 * np.ones((64, 256, 3), dtype="uint8"))
        reader.readtext(blank, detail=0)
        logger.info("EasyOCR pre-warm complete — ready for requests")
    except Exception as exc:
        logger.warning("EasyOCR pre-warm failed (will load on first request): %s", exc)


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Upload ──────────────────────────────────────────────────────────────
@app.post("/upload", response_model=UploadResponse)
@limiter.limit("20/minute")
async def upload_document(
    request: Request,
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")
    validate_upload(doc_type, file.filename)

    doc_id = str(uuid.uuid4())
    await save_upload(doc_id, file)

    doc = Document(
        id=doc_id,
        doc_type=doc_type,
        status="Pending",
        original_filename=file.filename,
    )
    db.add(doc)
    db.commit()

    return UploadResponse(doc_id=doc_id, doc_type=doc_type)


# ── Analyze ─────────────────────────────────────────────────────────────
@app.post("/analyze/{doc_id}", response_model=AnalyzeResponse)
@limiter.limit("20/minute")
async def analyze(request: Request, doc_id: str, db: Session = Depends(get_db), _: None = Depends(require_api_key)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = get_upload_path(doc_id)
    if not file_path:
        raise HTTPException(status_code=404, detail="Upload file not found")

    # Mark as Processing immediately so the frontend shows progress
    doc.status = "Processing"
    db.commit()

    # Run CPU-bound OCR in thread pool — keeps event loop free
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _ocr_executor,
        analyze_document,
        doc.doc_type,
        str(file_path),
        doc_id,
    )
    db_data = doc_to_db_json(result)

    doc.confidence_score = db_data["confidence_score"]
    doc.status = db_data["status"]
    doc.flags = db_data["flags_json"]
    doc.extracted_fields = db_data["fields_json"]
    doc.text_source = db_data["text_source"]
    doc.masked_image_path = db_data["masked_image_path"]
    doc.full_text = db_data["full_text"]
    doc.score_breakdown = db_data["score_breakdown_json"]
    doc.ocr_confidence = db_data["ocr_confidence"]
    doc.image_base64 = db_data.get("image_base64")
    doc.masked_image_base64 = db_data.get("masked_image_base64")
    doc.gemini_model = db_data.get("gemini_model")
    doc.gemini_raw_json = db_data.get("gemini_raw_json")
    doc.forgery_score = db_data.get("forgery_score")
    doc.forgery_reason = db_data.get("forgery_reason")
    doc.ai_confidence = db_data.get("ai_confidence")
    doc.ai_powered = db_data.get("ai_powered", False)
    doc.gemini_key_index = db_data.get("gemini_key_index")
    db.commit()

    return AnalyzeResponse(
        doc_id=doc_id,
        doc_type=doc.doc_type,
        confidence_score=db_data["confidence_score"],
        flags=json.loads(db_data["flags_json"]),
        extracted_fields=json.loads(db_data["fields_json"]),
        status=db_data["status"],
        text_source=db_data["text_source"],
        score_breakdown=json.loads(db_data["score_breakdown_json"]),
        full_text=db_data["full_text"],
        ocr_confidence=db_data["ocr_confidence"],
        ai_powered=db_data.get("ai_powered"),
        forgery_score=db_data.get("forgery_score"),
        forgery_reason=db_data.get("forgery_reason"),
        ai_confidence=db_data.get("ai_confidence"),
    )


# ── Status ──────────────────────────────────────────────────────────────
@app.get("/status/{doc_id}", response_model=StatusResponse)
def status(doc_id: str, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _status_response(doc)


# ── Documents ───────────────────────────────────────────────────────────
@app.get("/documents", response_model=list[StatusResponse])
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    return [_status_response(d) for d in docs]


# ── Queue ───────────────────────────────────────────────────────────────
@app.get("/queue", response_model=list[StatusResponse])
def queue(db: Session = Depends(get_db)):
    docs = (
        db.query(Document)
        .filter(Document.status.in_(["Red Flagged", "Manual Review Required", "Pending Verification", "Low Confidence"]))
        .order_by(Document.created_at.desc())
        .all()
    )
    return [_status_response(d) for d in docs]


# ── Dashboard Stats ────────────────────────────────────────────────────
@app.get("/documents/stats", response_model=StatsResponse)
def document_stats(db: Session = Depends(get_db)):
    total = db.query(func.count(Document.id)).scalar() or 0

    verified = db.query(func.count(Document.id)).filter(
        Document.status.in_(["Auto-Verified", "Verified", "System Verified"])
    ).scalar() or 0

    pending_review = db.query(func.count(Document.id)).filter(
        Document.status.in_(["Manual Review Required", "Pending Verification", "Low Confidence"])
    ).scalar() or 0

    rejected = db.query(func.count(Document.id)).filter(
        Document.status.in_(["Rejected", "Red Flagged"])
    ).scalar() or 0

    pending = db.query(func.count(Document.id)).filter(
        Document.status == "Pending"
    ).scalar() or 0

    avg_conf = db.query(func.avg(Document.confidence_score)).filter(
        Document.confidence_score.isnot(None)
    ).scalar() or 0.0

    avg_ocr = db.query(func.avg(Document.ocr_confidence)).filter(
        Document.ocr_confidence.isnot(None)
    ).scalar() or 0.0

    # By doc type
    type_counts = db.query(Document.doc_type, func.count(Document.id)).group_by(Document.doc_type).all()
    by_doc_type = {t: c for t, c in type_counts}

    # Recent 10
    recent = db.query(Document).order_by(Document.created_at.desc()).limit(10).all()

    return StatsResponse(
        total=total,
        verified=verified,
        pending_review=pending_review,
        rejected=rejected,
        pending=pending,
        avg_confidence=round(float(avg_conf), 1),
        avg_ocr_accuracy=round(float(avg_ocr), 3),
        by_doc_type=by_doc_type,
        recent_uploads=[_status_response(d) for d in recent],
    )


# ── Manual Review ───────────────────────────────────────────────────────
@app.post("/manual-review/{doc_id}", response_model=StatusResponse)
def manual_review(
    doc_id: str,
    body: ManualReviewRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if body.action == "approve":
        doc.status = "Verified"
    elif body.action == "reject":
        doc.status = "Rejected"
    elif body.action == "request_reupload":
        doc.status = "Re-upload Requested"

    if body.notes:
        doc.reviewer_notes = body.notes
    if body.reviewer_name:
        doc.reviewed_by = body.reviewer_name
    doc.reviewed_at = datetime.now(timezone.utc)

    # If HR edited extracted fields, save them
    if body.edited_fields:
        existing = json.loads(doc.extracted_fields or "{}")
        existing.update(body.edited_fields)
        doc.extracted_fields = json.dumps(existing, default=str)

    db.commit()
    return _status_response(doc)


# ── Experience Verification ─────────────────────────────────────────────
@app.post("/verify-experience/{doc_id}", response_model=VerifyExperienceResponse)
def verify_experience_endpoint(
    doc_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.doc_type != "experience":
        raise HTTPException(status_code=400, detail="Only experience letters can be verified")

    outcome = verify_experience(doc)
    doc.verification_status = outcome["verification_status"]
    doc.flags = json.dumps(outcome["flags"])
    if outcome["verification_status"] == "System Verified":
        doc.status = "System Verified"
    elif outcome["verification_status"] == "Red Flagged":
        doc.status = "Red Flagged"
    else:
        doc.status = outcome["verification_status"]
    db.commit()

    return VerifyExperienceResponse(
        doc_id=doc_id,
        verification_status=outcome["verification_status"],
        flags=outcome["flags"],
        demo_mode=outcome.get("demo_mode", False),
    )


# ── Gov Verify Stub ────────────────────────────────────────────────────
@app.post("/gov-verify/{doc_id}", response_model=GovVerifyResponse)
def gov_verify(doc_id: str, db: Session = Depends(get_db), _: None = Depends(require_api_key)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    stub = gov_verify_stub(doc.doc_type)
    return GovVerifyResponse(verified=stub["verified"], message=stub["message"])


# ── Masked Image ────────────────────────────────────────────────────────
@app.get("/masked/{doc_id}")
def get_masked(doc_id: str, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    # Try file on disk first
    if doc.masked_image_path:
        path = Path(doc.masked_image_path)
        if path.exists():
            return FileResponse(path, media_type="image/jpeg", filename=f"{doc_id}_masked.jpg")
    # Fallback: serve from base64 in Supabase
    if doc.masked_image_base64:
        img_bytes = base64.b64decode(doc.masked_image_base64)
        return Response(content=img_bytes, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Masked image not available")


# ── Original Image ──────────────────────────────────────────────────────
@app.get("/original/{doc_id}")
def get_original(doc_id: str, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    # Try files on disk first
    for ext in [".jpg", ".jpeg", ".png", ".pdf"]:
        path = ORIGINAL_UPLOADS / f"{doc_id}{ext}"
        if path.exists():
            media = "image/jpeg" if ext in (".jpg", ".jpeg") else ("image/png" if ext == ".png" else "application/pdf")
            return FileResponse(path, media_type=media, filename=f"{doc_id}_original{ext}")
    upload_path = get_upload_path(doc_id)
    if upload_path and upload_path.exists():
        ext = upload_path.suffix
        media = "image/jpeg" if ext in (".jpg", ".jpeg") else ("image/png" if ext == ".png" else "application/pdf")
        return FileResponse(upload_path, media_type=media, filename=f"{doc_id}_original{ext}")
    # Fallback: serve from base64 in Supabase
    if doc.image_base64:
        img_bytes = base64.b64decode(doc.image_base64)
        return Response(content=img_bytes, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Original file not available")


# ── Image Base64 endpoint (for frontend) ────────────────────────────────
@app.get("/image-base64/{doc_id}")
def get_image_base64(doc_id: str, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "doc_id": doc_id,
        "image_base64": doc.image_base64,
        "masked_image_base64": doc.masked_image_base64,
    }


# ── Download Text ───────────────────────────────────────────────────────
@app.get("/download/text/{doc_id}")
def download_text(doc_id: str, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    text = doc.full_text or ""
    if not text.strip():
        raise HTTPException(status_code=404, detail="No extracted text available")
    return StreamingResponse(
        iter([text.encode("utf-8")]),
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{doc_id}_extracted.txt"'},
    )


# ── Download JSON ───────────────────────────────────────────────────────
@app.get("/download/json/{doc_id}")
def download_json(doc_id: str, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    data = {
        "doc_id": doc.id,
        "doc_type": doc.doc_type,
        "status": doc.status,
        "confidence_score": doc.confidence_score,
        "ocr_confidence": doc.ocr_confidence,
        "score_breakdown": json.loads(doc.score_breakdown or "{}"),
        "flags": json.loads(doc.flags or "[]"),
        "extracted_fields": json.loads(doc.extracted_fields or "{}"),
        "text_source": doc.text_source,
        "verification_status": doc.verification_status,
        "reviewer_notes": doc.reviewer_notes,
        "reviewed_by": doc.reviewed_by,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }
    content = json.dumps(data, indent=2, ensure_ascii=False)
    return StreamingResponse(
        iter([content.encode("utf-8")]),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{doc_id}_report.json"'},
    )


# ── Download Masked ─────────────────────────────────────────────────────
@app.get("/download/masked/{doc_id}")
def download_masked(doc_id: str, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc or not doc.masked_image_path:
        raise HTTPException(status_code=404, detail="Masked image not available")
    path = Path(doc.masked_image_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Masked image file missing")
    return FileResponse(path, media_type="image/jpeg", filename=f"{doc_id}_masked.jpg",
                        headers={"Content-Disposition": f'attachment; filename="{doc_id}_masked.jpg"'})


# ── Helper ──────────────────────────────────────────────────────────────
def _status_response(doc: Document) -> StatusResponse:
    return StatusResponse(
        doc_id=doc.id,
        doc_type=doc.doc_type,
        status=doc.status,
        confidence_score=doc.confidence_score,
        flags=json.loads(doc.flags or "[]"),
        extracted_fields=json.loads(doc.extracted_fields or "{}"),
        text_source=doc.text_source,
        verification_status=doc.verification_status,
        masked_image_path=doc.masked_image_path,
        created_at=doc.created_at.isoformat() if doc.created_at else None,
        score_breakdown=json.loads(doc.score_breakdown or "{}") if doc.score_breakdown else None,
        full_text=doc.full_text,
        ocr_confidence=doc.ocr_confidence,
        reviewer_notes=doc.reviewer_notes,
        reviewed_by=doc.reviewed_by,
        original_filename=doc.original_filename,
        ai_powered=doc.ai_powered,
        forgery_score=doc.forgery_score,
        forgery_reason=doc.forgery_reason,
        ai_confidence=doc.ai_confidence,
    )
