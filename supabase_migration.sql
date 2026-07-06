-- DocVerify AI — Supabase Schema
-- Run this in your Supabase SQL Editor: https://supabase.com/dashboard/project/uymdjpfognbqcsotjztr/sql

CREATE TABLE IF NOT EXISTS documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  doc_type VARCHAR(32) NOT NULL,
  status VARCHAR(64) DEFAULT 'Pending',
  confidence_score DOUBLE PRECISION,
  flags TEXT DEFAULT '[]',
  extracted_fields TEXT DEFAULT '{}',
  text_source VARCHAR(16),
  original_filename VARCHAR(255),
  masked_image_path VARCHAR(512),
  verification_status VARCHAR(64),
  full_text TEXT,
  score_breakdown TEXT,
  ocr_confidence DOUBLE PRECISION,
  reviewer_notes TEXT,
  reviewed_by VARCHAR(128),
  reviewed_at TIMESTAMPTZ,
  image_base64 TEXT,
  masked_image_base64 TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for dashboard queries
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_doc_type ON documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at DESC);

-- Auto-update updated_at on row changes
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_documents_updated_at ON documents;
CREATE TRIGGER update_documents_updated_at
  BEFORE UPDATE ON documents
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();
