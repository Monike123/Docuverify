from typing import Any

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    doc_id: str
    doc_type: str


class AnalyzeResponse(BaseModel):
    doc_id: str
    doc_type: str
    confidence_score: float
    flags: list[str]
    extracted_fields: dict[str, Any]
    status: str
    text_source: str | None = None
    score_breakdown: dict[str, float] | None = None
    full_text: str | None = None
    ocr_confidence: float | None = None
    ai_powered: bool | None = None
    forgery_score: float | None = None
    forgery_reason: str | None = None
    ai_confidence: float | None = None


class StatusResponse(BaseModel):
    doc_id: str
    doc_type: str
    status: str
    confidence_score: float | None
    flags: list[str]
    extracted_fields: dict[str, Any]
    text_source: str | None = None
    verification_status: str | None = None
    masked_image_path: str | None = None
    created_at: str | None = None
    score_breakdown: dict[str, float] | None = None
    full_text: str | None = None
    ocr_confidence: float | None = None
    reviewer_notes: str | None = None
    reviewed_by: str | None = None
    original_filename: str | None = None
    ai_powered: bool | None = None
    forgery_score: float | None = None
    forgery_reason: str | None = None
    ai_confidence: float | None = None


class ManualReviewRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject|request_reupload)$")
    notes: str | None = None
    reviewer_name: str | None = None
    edited_fields: dict[str, Any] | None = None


class VerifyExperienceResponse(BaseModel):
    doc_id: str
    verification_status: str
    flags: list[str]
    demo_mode: bool = False


class GovVerifyResponse(BaseModel):
    verified: bool
    message: str


class StatsResponse(BaseModel):
    total: int
    verified: int
    pending_review: int
    rejected: int
    pending: int
    avg_confidence: float
    avg_ocr_accuracy: float
    by_doc_type: dict[str, int]
    recent_uploads: list[StatusResponse]
