-- DocVerify AI — Supabase Migration
-- Run this in the Supabase SQL Editor: https://app.supabase.com/project/uymdjpfognbqcsotjztr/sql

-- Create documents table
CREATE TABLE IF NOT EXISTS documents (
    id               VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    doc_type         VARCHAR(32)  NOT NULL,
    status           VARCHAR(64)  NOT NULL DEFAULT 'Pending',
    confidence_score FLOAT,
    flags            TEXT         NOT NULL DEFAULT '[]',
    extracted_fields TEXT         NOT NULL DEFAULT '{}',
    text_source      VARCHAR(16),
    original_filename VARCHAR(255),
    masked_image_path VARCHAR(512),
    verification_status VARCHAR(64),

    -- OCR data
    full_text        TEXT,
    score_breakdown  TEXT,
    ocr_confidence   FLOAT,

    -- Review fields
    reviewer_notes   TEXT,
    reviewed_by      VARCHAR(128),
    reviewed_at      TIMESTAMPTZ,

    -- Image storage as base64 for cloud persistence
    image_base64        TEXT,
    masked_image_base64 TEXT,

    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Gemini AI audit fields (additive — safe on existing tables)
ALTER TABLE documents ADD COLUMN IF NOT EXISTS gemini_model VARCHAR(64);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS gemini_raw_json TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS forgery_score FLOAT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS forgery_reason TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS ai_confidence FLOAT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS ai_powered BOOLEAN DEFAULT FALSE;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS gemini_key_index SMALLINT;

-- Index for fast queries
CREATE INDEX IF NOT EXISTS idx_documents_doc_type    ON documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_documents_status      ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_created_at  ON documents(created_at DESC);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_documents_updated_at ON documents;
CREATE TRIGGER trg_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Enable Row Level Security (optional, adjust for your auth setup)
-- ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
