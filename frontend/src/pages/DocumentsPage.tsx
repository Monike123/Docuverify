import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { HiOutlineSearch } from 'react-icons/hi';
import { listDocuments } from '../api';
import type { DocumentResult } from '../api';

const DOC_TYPE_LABELS: Record<string, string> = {
  aadhaar: 'Aadhaar', pan: 'PAN', caste: 'Caste', experience: 'Experience',
  education: 'Education', resume: 'Resume', general: 'General',
};

function getStatusClass(status: string) {
  const s = status.toLowerCase();
  if (s.includes('verified') || s.includes('auto')) return 'verified';
  if (s.includes('pending')) return 'pending';
  if (s.includes('review') || s.includes('low')) return 'review';
  return 'rejected';
}

function formatDate(dateStr: string | null) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const navigate = useNavigate();

  useEffect(() => {
    listDocuments().then(setDocs).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const filtered = docs.filter(d => {
    if (filterType !== 'all' && d.doc_type !== filterType) return false;
    if (filterStatus !== 'all') {
      const s = d.status.toLowerCase();
      if (filterStatus === 'verified' && !(s.includes('verified') || s.includes('auto'))) return false;
      if (filterStatus === 'pending' && !s.includes('pending')) return false;
      if (filterStatus === 'review' && !(s.includes('review') || s.includes('low'))) return false;
      if (filterStatus === 'rejected' && !(s.includes('rejected') || s.includes('flagged'))) return false;
    }
    if (search) {
      const q = search.toLowerCase();
      return (d.original_filename?.toLowerCase().includes(q)) ||
             d.doc_id.toLowerCase().includes(q) ||
             d.doc_type.includes(q);
    }
    return true;
  });

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">All Documents</h1>
          <p className="page-subtitle">{docs.length} total documents processed</p>
        </div>
      </div>

      <div className="page-body">
        {/* Filters */}
        <div className="card fade-in" style={{ marginBottom: '16px' }}>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: '200px', position: 'relative' }}>
              <HiOutlineSearch style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                className="form-input"
                placeholder="Search by filename or ID..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ paddingLeft: '36px' }}
              />
            </div>
            <select className="form-select" value={filterType} onChange={(e) => setFilterType(e.target.value)} style={{ width: '160px' }}>
              <option value="all">All Types</option>
              {Object.entries(DOC_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <select className="form-select" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} style={{ width: '160px' }}>
              <option value="all">All Status</option>
              <option value="verified">Verified</option>
              <option value="pending">Pending</option>
              <option value="review">Needs Review</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>
        </div>

        {/* Table */}
        <div className="card fade-in">
          {loading ? (
            <div className="loading-overlay"><div className="spinner" /><span>Loading documents...</span></div>
          ) : filtered.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📂</div>
              <div className="empty-state-title">No documents found</div>
            </div>
          ) : (
            <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>File</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Confidence</th>
                  <th>OCR</th>
                  <th>Flags</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(doc => (
                  <tr key={doc.doc_id} onClick={() => navigate(`/result/${doc.doc_id}`)}>
                    <td style={{ color: 'var(--text-primary)', fontWeight: 500, maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {doc.original_filename || doc.doc_id.slice(0, 10) + '...'}
                    </td>
                    <td>{DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type}</td>
                    <td><span className={`status-badge ${getStatusClass(doc.status)}`}>{doc.status}</span></td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                      {doc.confidence_score != null ? `${doc.confidence_score}%` : '—'}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)' }}>
                      {doc.ocr_confidence != null ? `${(doc.ocr_confidence * 100).toFixed(0)}%` : '—'}
                    </td>
                    <td>
                      {doc.flags.length > 0 ? (
                        <span className="flag-tag">{doc.flags.length} flags</span>
                      ) : (
                        <span style={{ color: 'var(--color-success)', fontSize: '12px' }}>✓ Clean</span>
                      )}
                    </td>
                    <td style={{ whiteSpace: 'nowrap' }}>{formatDate(doc.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
