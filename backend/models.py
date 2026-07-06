import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    # Use native PostgreSQL UUID — matches Supabase schema exactly
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),   # store/return as str, not Python uuid object
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="Pending")
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    flags: Mapped[str] = mapped_column(Text, default="[]")
    extracted_fields: Mapped[str] = mapped_column(Text, default="{}")
    text_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    masked_image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    verification_status: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # OCR data
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    score_breakdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Review fields
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Image storage as base64 (cloud-safe persistence for HF Spaces)
    image_base64: Mapped[str | None] = mapped_column(Text, nullable=True)
    masked_image_base64: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Gemini AI audit trail
    gemini_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gemini_raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    forgery_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    forgery_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_powered: Mapped[bool | None] = mapped_column(Boolean, default=False)
    gemini_key_index: Mapped[int | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
