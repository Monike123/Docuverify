import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { HiOutlineShieldCheck, HiOutlineXCircle, HiOutlineEye } from 'react-icons/hi';
import { getQueue, manualReview } from '../api';
import type { DocumentResult } from '../api';

const DOC_TYPE_LABELS: Record<string, string> = {
  aadhaar: 'Aadhaar', pan: 'PAN', caste: 'Caste', experience: 'Experience',
  education: 'Education', resume: 'Resume', general: 'General',
};

export default function ReviewPage() {
  const [docs, setDocs] = useState<DocumentResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const navigate = useNavigate();

  const loadQueue = () => {
    setLoading(true);
    getQueue().then(setDocs).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(loadQueue, []);

  const handleAction = async (docId: string, action: string) => {
    setActionLoading(docId);
    const user = localStorage.getItem('docverify_user') || 'HR Admin';
    try {
      await manualReview(docId, action, undefined, user);
      setDocs(prev => prev.filter(d => d.doc_id !== docId));
    } catch {}
    setActionLoading(null);
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Review Queue</h1>
          <p className="page-subtitle">{docs.length} documents awaiting review</p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={loadQueue}>Refresh</button>
      </div>

      <div className="page-body">
        {loading ? (
          <div className="loading-overlay"><div className="spinner" /><span>Loading queue...</span></div>
        ) : docs.length === 0 ? (
          <div className="empty-state fade-in">
            <div className="empty-state-icon">✅</div>
            <div className="empty-state-title">Queue is empty</div>
            <p>All documents have been reviewed.</p>
          </div>
        ) : (
          <div style={{ display: 'grid', gap: '12px' }}>
            {docs.map(doc => (
              <div key={doc.doc_id} className="card slide-in" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
                    {doc.original_filename || doc.doc_id.slice(0, 12) + '...'}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                    <span>{DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type}</span>
                    <span>Confidence: <strong style={{ color: 'var(--text-secondary)' }}>{doc.confidence_score ?? 0}%</strong></span>
                    {doc.flags.length > 0 && <span className="flag-tag">{doc.flags[0]}{doc.flags.length > 1 ? ` +${doc.flags.length - 1}` : ''}</span>}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
                  <button className="btn btn-secondary btn-sm" onClick={() => navigate(`/result/${doc.doc_id}`)}>
                    <HiOutlineEye /> View
                  </button>
                  <button
                    className="btn btn-success btn-sm"
                    onClick={() => handleAction(doc.doc_id, 'approve')}
                    disabled={actionLoading === doc.doc_id}
                  >
                    <HiOutlineShieldCheck /> Approve
                  </button>
                  <button
                    className="btn btn-danger btn-sm"
                    onClick={() => handleAction(doc.doc_id, 'reject')}
                    disabled={actionLoading === doc.doc_id}
                  >
                    <HiOutlineXCircle /> Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
