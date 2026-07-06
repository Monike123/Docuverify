import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  HiOutlineDownload, HiOutlineShieldCheck, HiOutlineDocumentText,
  HiOutlinePhotograph, HiOutlineEye, HiOutlineChevronLeft,
  HiOutlineExclamationCircle, HiOutlineCheckCircle, HiOutlineShieldExclamation,
} from 'react-icons/hi';
import {
  getDocumentStatus, getOriginalUrl, getMaskedUrl,
  getDownloadJsonUrl, manualReview,
} from '../api';
import type { DocumentResult } from '../api';

// ── Doc type display names ────────────────────────────────────────────
const DOC_TYPE_LABELS: Record<string, string> = {
  aadhaar: 'Aadhaar Card', pan: 'PAN Card', caste: 'Caste Certificate',
  experience: 'Experience Letter', education: 'Education Certificate',
  resume: 'Resume / CV', general: 'General Document',
};

// ── Human-readable field labels (hides internal keys) ────────────────
const FIELD_LABELS: Record<string, string> = {
  name:                    'Full Name',
  date_of_birth:           'Date of Birth',
  year_of_birth:           'Year of Birth',
  gender:                  'Gender',
  aadhaar_number_display:  'Aadhaar Number',
  address:                 'Address',
  pincode:                 'PIN Code',
  state:                   'State',
  pan_number:              'PAN Number',
  father_name:             "Father's Name",
  dob:                     'Date of Birth',
  company_name:            'Organisation',
  employee_name:           'Employee Name',
  designation:             'Designation',
  joining_date:            'Joining Date',
  relieving_date:          'Relieving Date',
  employment_duration:     'Duration',
  salary:                  'Salary',
  institute_name:          'Institution',
  degree:                  'Degree / Programme',
  branch:                  'Branch / Specialisation',
  roll_number:             'Roll Number',
  passing_year:            'Year of Passing',
  percentage_or_grade:     'Grade / Percentage',
  category:                'Category',
  certificate_number:      'Certificate Number',
  issuing_authority:       'Issued By',
};

// ── Internal-only keys — NEVER shown to user ─────────────────────────
const HIDDEN_KEYS = new Set([
  'side', 'qr_detected', 'aadhaar_masked', 'is_masked',
  'aadhaar_number_raw', 'pan_validated', 'signature_present',
  'aadhaar_number', // raw unredacted
]);

// ── Flag → human message ─────────────────────────────────────────────
const FLAG_MESSAGES: Record<string, { label: string; severity: 'warning' | 'critical' }> = {
  MISSING_NAME:                  { label: 'Name could not be read', severity: 'warning' },
  MISSING_DATE_OF_BIRTH:         { label: 'Date of birth not found', severity: 'warning' },
  MISSING_AADHAAR_NUMBER_RAW:    { label: 'Aadhaar number not detected', severity: 'critical' },
  AADHAAR_CHECKSUM_MISMATCH:     { label: 'Aadhaar number appears invalid', severity: 'critical' },
  AADHAAR_NUMBER_INCOMPLETE:     { label: 'Aadhaar number may be cut off', severity: 'warning' },
  INVALID_DATE_FORMAT:           { label: 'Date format unrecognised', severity: 'warning' },
  INVALID_PINCODE:               { label: 'PIN code looks incorrect', severity: 'warning' },
  LOW_OCR_CONFIDENCE:            { label: 'Image quality is low — results may be less accurate', severity: 'warning' },
  POSSIBLE_DOCUMENT_MANIPULATION: { label: 'Document may have been digitally altered', severity: 'critical' },
  MISSING_PAN_NUMBER:            { label: 'PAN number not detected', severity: 'critical' },
  INVALID_PAN_FORMAT:            { label: 'PAN format is incorrect', severity: 'critical' },
  NO_PAN_OCR:                    { label: 'PAN number could not be read', severity: 'critical' },
  TEXT_EXTRACT_FAILED:           { label: 'Could not read document — please upload a clearer image', severity: 'critical' },
  LOW_IMAGE_QUALITY:             { label: 'Image resolution is too low', severity: 'warning' },
};

function getFlagInfo(flag: string) {
  return FLAG_MESSAGES[flag] ?? { label: flag.replace(/_/g, ' ').toLowerCase(), severity: 'warning' as const };
}

function confLevel(score: number | null) {
  if (score == null) return 'low';
  if (score >= 75) return 'high';
  if (score >= 50) return 'medium';
  return 'low';
}

function confLabel(score: number | null) {
  if (score == null) return 'Unable to verify';
  if (score >= 80) return 'High Confidence';
  if (score >= 60) return 'Moderate Confidence';
  if (score >= 40) return 'Low Confidence';
  return 'Very Low — Manual Review Needed';
}

function getStatusClass(status: string) {
  const s = status.toLowerCase();
  if (s.includes('verified') || s.includes('auto')) return 'verified';
  if (s.includes('pending')) return 'pending';
  if (s.includes('review') || s.includes('low')) return 'review';
  return 'rejected';
}

export default function ResultPage() {
  const { docId } = useParams();
  const navigate = useNavigate();
  const [doc, setDoc] = useState<DocumentResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [imageTab, setImageTab] = useState<'original' | 'masked'>('original');
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewing, setReviewing] = useState(false);

  useEffect(() => {
    if (!docId) return;
    getDocumentStatus(docId)
      .then(setDoc)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [docId]);

  const handleReview = async (action: string) => {
    if (!docId) return;
    setReviewing(true);
    try {
      const user = localStorage.getItem('docverify_user') || 'HR Admin';
      const result = await manualReview(docId, action, reviewNotes, user);
      setDoc(result);
      setReviewNotes('');
    } catch {}
    setReviewing(false);
  };

  if (loading) {
    return (
      <>
        <div className="page-header"><div><h1 className="page-title">Document Details</h1></div></div>
        <div className="page-body"><div className="loading-overlay"><div className="spinner" /><span>Analysing document…</span></div></div>
      </>
    );
  }

  if (!doc) {
    return (
      <>
        <div className="page-header"><div><h1 className="page-title">Not Found</h1></div></div>
        <div className="page-body"><div className="empty-state"><div className="empty-state-title">Document not found</div></div></div>
      </>
    );
  }

  const level = confLevel(doc.confidence_score);

  // Filter extracted fields — hide internal keys, sort by priority
  const FIELD_ORDER = ['name','aadhaar_number_display','pan_number','date_of_birth','dob','year_of_birth','gender','father_name','address','pincode','state','company_name','employee_name','designation','joining_date','relieving_date','employment_duration','salary','institute_name','degree','branch','roll_number','passing_year','percentage_or_grade','category','certificate_number','issuing_authority'];
  const visibleFields = Object.entries(doc.extracted_fields)
    .filter(([k]) => !HIDDEN_KEYS.has(k))
    .sort(([a], [b]) => {
      const ai = FIELD_ORDER.indexOf(a);
      const bi = FIELD_ORDER.indexOf(b);
      return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    });

  const criticalFlags = doc.flags.filter(f => getFlagInfo(f).severity === 'critical');
  const warningFlags  = doc.flags.filter(f => getFlagInfo(f).severity !== 'critical');

  // Forgery from flags
  const isSuspicious = doc.flags.includes('POSSIBLE_DOCUMENT_MANIPULATION');

  return (
    <>
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button className="btn btn-secondary btn-sm" onClick={() => navigate(-1)}><HiOutlineChevronLeft /> Back</button>
          <div>
            <h1 className="page-title">{DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type}</h1>
            <p className="page-subtitle">{doc.original_filename || doc.doc_id.slice(0, 12)}…</p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <a className="btn btn-secondary btn-sm" href={getDownloadJsonUrl(doc.doc_id)} target="_blank">
            <HiOutlineDownload /> Export Report
          </a>
        </div>
      </div>

      <div className="page-body">

        {/* ── Confidence + Status bar ─────────────────────────────────── */}
        <div className="stats-grid fade-in" style={{ gridTemplateColumns: '220px 1fr auto', marginBottom: '20px', gap: '16px' }}>

          {/* Big score */}
          <div className="card" style={{ textAlign: 'center', padding: '28px 24px' }}>
            <div className={`confidence-score-display ${level}`}>{doc.confidence_score ?? 0}</div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)', marginTop: '6px' }}>
              {confLabel(doc.confidence_score)}
            </div>
            <div className="confidence-meter" style={{ marginTop: '12px' }}>
              <div className="confidence-bar-bg">
                <div className={`confidence-bar-fill ${level}`} style={{ width: `${doc.confidence_score ?? 0}%` }} />
              </div>
            </div>
            <div className={`status-badge ${getStatusClass(doc.status)}`} style={{ marginTop: '12px', display: 'inline-block' }}>
              {doc.status}
            </div>
          </div>

          {/* Forgery / integrity panel */}
          <div className="card" style={{ padding: '20px 24px' }}>
            <div className="card-title" style={{ marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <HiOutlineShieldExclamation style={{ color: isSuspicious ? 'var(--danger)' : 'var(--success)' }} />
              Document Integrity
              {/* AI badge */}
              <span style={{
                marginLeft: 'auto', fontSize: '11px', fontWeight: 600,
                background: doc.ai_powered ? 'var(--accent-glow)' : 'rgba(100,116,139,0.12)',
                color: doc.ai_powered ? 'var(--accent-primary)' : 'var(--text-muted)',
                border: `1px solid ${doc.ai_powered ? 'var(--border-active)' : 'var(--border-secondary)'}`,
                borderRadius: '20px', padding: '2px 10px',
              }}>
                {doc.ai_powered ? '✦ AI Powered' : '⚙ OCR Analysis'}
              </span>
            </div>

            {isSuspicious ? (
              <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '8px', padding: '12px 16px', color: '#fca5a5' }}>
                <div style={{ fontWeight: 600, marginBottom: '4px' }}>⚠ Possible manipulation detected</div>
                <div style={{ fontSize: '13px', opacity: 0.85 }}>
                  {doc.forgery_reason
                    ? doc.forgery_reason
                    : 'This document shows signs of digital editing. Recommend collecting the original physical document for manual review.'}
                </div>
              </div>
            ) : (
              <div style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)', borderRadius: '8px', padding: '12px 16px', color: '#86efac' }}>
                <div style={{ fontWeight: 600, marginBottom: '4px' }}>✓ No manipulation detected</div>
                <div style={{ fontSize: '13px', opacity: 0.85 }}>
                  Document integrity checks passed. No signs of digital alteration found.
                </div>
              </div>
            )}

            {/* Critical flags */}
            {criticalFlags.length > 0 && (
              <div style={{ marginTop: '12px' }}>
                {criticalFlags.map((f, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#fca5a5', fontSize: '13px', marginBottom: '6px' }}>
                    <HiOutlineExclamationCircle style={{ flexShrink: 0 }} />
                    {getFlagInfo(f).label}
                  </div>
                ))}
              </div>
            )}

            {/* Warnings */}
            {warningFlags.length > 0 && (
              <div style={{ marginTop: '8px' }}>
                {warningFlags.map((f, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#fde68a', fontSize: '13px', marginBottom: '6px' }}>
                    <HiOutlineExclamationCircle style={{ flexShrink: 0 }} />
                    {getFlagInfo(f).label}
                  </div>
                ))}
              </div>
            )}

            {doc.flags.length === 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#86efac', fontSize: '13px', marginTop: '10px' }}>
                <HiOutlineCheckCircle /> All validation checks passed
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="card" style={{ minWidth: '160px', padding: '20px 16px' }}>
            <div className="card-title" style={{ marginBottom: '12px' }}>Actions</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <button className="btn btn-success btn-sm" onClick={() => handleReview('approve')} disabled={reviewing}>
                <HiOutlineShieldCheck /> Approve
              </button>
              <button className="btn btn-danger btn-sm" onClick={() => handleReview('reject')} disabled={reviewing}>
                Reject
              </button>
            </div>
            {doc.reviewed_by && (
              <div style={{ marginTop: '10px', fontSize: '11px', color: 'var(--text-muted)' }}>
                Reviewed by: {doc.reviewed_by}
              </div>
            )}
          </div>
        </div>

        {/* ── Detail layout ─────────────────────────────────────────────── */}
        <div className="detail-layout fade-in">

          {/* Left: Image */}
          <div>
            <div className="detail-section" style={{ marginBottom: '16px' }}>
              <div className="image-viewer">
                <div className="image-viewer-tabs">
                  <button className={`image-viewer-tab ${imageTab === 'original' ? 'active' : ''}`} onClick={() => setImageTab('original')}>
                    <HiOutlinePhotograph /> Original
                  </button>
                  {doc.masked_image_path && (
                    <button className={`image-viewer-tab ${imageTab === 'masked' ? 'active' : ''}`} onClick={() => setImageTab('masked')}>
                      <HiOutlineEye /> PII Redacted
                    </button>
                  )}
                </div>
                <img
                  src={imageTab === 'masked' ? getMaskedUrl(doc.doc_id) : getOriginalUrl(doc.doc_id)}
                  alt={imageTab === 'masked' ? 'Redacted' : 'Original'}
                  style={{ maxHeight: '450px', objectFit: 'contain', background: '#000' }}
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                />
              </div>
            </div>

            {/* Raw text — collapsed by default, only for power users */}
            {doc.full_text && (
              <details className="detail-section">
                <summary style={{ cursor: 'pointer', fontSize: '13px', color: 'var(--text-tertiary)', padding: '8px 0' }}>
                  <HiOutlineDocumentText style={{ display: 'inline', marginRight: '6px' }} />
                  Raw Extracted Text
                </summary>
                <div className="text-viewer" style={{ marginTop: '8px' }}>{doc.full_text}</div>
              </details>
            )}
          </div>

          {/* Right: Fields + Review */}
          <div>
            {/* Extracted fields — clean labels only */}
            <div className="detail-section" style={{ marginBottom: '16px' }}>
              <div className="detail-section-title">📋 Extracted Information</div>

              {visibleFields.length === 0 ? (
                <div style={{ color: 'var(--text-muted)', fontSize: '13px', padding: '12px 0' }}>
                  No information could be extracted from this document.
                </div>
              ) : (
                <div className="field-grid" style={{ gridTemplateColumns: '1fr' }}>
                  {visibleFields.map(([key, value]) => (
                    <div className="field-item" key={key}>
                      <div className="field-key">
                        {FIELD_LABELS[key] ?? key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                      </div>
                      <div className="field-value">
                        {typeof value === 'boolean'
                          ? (value ? 'Yes' : 'No')
                          : typeof value === 'object'
                          ? JSON.stringify(value)
                          : String(value)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Review Notes */}
            <div className="detail-section">
              <div className="detail-section-title">📝 Review Notes</div>
              <textarea
                className="form-textarea"
                rows={3}
                placeholder="Add notes about this document…"
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
              />
              {doc.reviewer_notes && (
                <div style={{ marginTop: '10px', padding: '10px', background: 'var(--bg-primary)', borderRadius: 'var(--radius-sm)', fontSize: '13px', color: 'var(--text-secondary)' }}>
                  <strong>Previous notes:</strong> {doc.reviewer_notes}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
