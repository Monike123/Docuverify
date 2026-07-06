import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { HiOutlineDocumentText, HiOutlineShieldCheck, HiOutlineClock, HiOutlineXCircle, HiOutlineChartBar } from 'react-icons/hi';
import { getDashboardStats } from '../api';
import type { DashboardStats } from '../api';

const DOC_TYPE_LABELS: Record<string, string> = {
  aadhaar: 'Aadhaar Card',
  pan: 'PAN Card',
  caste: 'Caste Certificate',
  experience: 'Experience Letter',
  education: 'Education Certificate',
  resume: 'Resume / CV',
  general: 'General',
};

function getStatusClass(status: string) {
  const s = status.toLowerCase();
  if (s.includes('verified') || s.includes('auto')) return 'verified';
  if (s.includes('pending')) return 'pending';
  if (s.includes('review') || s.includes('low')) return 'review';
  return 'rejected';
}

function timeAgo(dateStr: string | null) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  const now = new Date();
  const diff = Math.floor((now.getTime() - d.getTime()) / 1000);
  if (diff < 60) return 'Just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    getDashboardStats()
      .then(setStats)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <>
        <div className="page-header">
          <div>
            <h1 className="page-title">Dashboard</h1>
            <p className="page-subtitle">Document verification overview</p>
          </div>
        </div>
        <div className="page-body">
          <div className="loading-overlay"><div className="spinner" /><span>Loading dashboard...</span></div>
        </div>
      </>
    );
  }

  if (!stats) {
    return (
      <>
        <div className="page-header">
          <div><h1 className="page-title">Dashboard</h1></div>
        </div>
        <div className="page-body">
          <div className="empty-state">
            <div className="empty-state-icon">📊</div>
            <div className="empty-state-title">Backend Offline</div>
            <p>Unable to connect to the verification engine. Check backend status.</p>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Real-time document verification metrics</p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/upload')}>
          <HiOutlineDocumentText /> Upload Document
        </button>
      </div>

      <div className="page-body">
        {/* Stats Grid */}
        <div className="stats-grid fade-in">
          <div className="stat-card">
            <div className="stat-icon primary"><HiOutlineDocumentText /></div>
            <div className="stat-content">
              <div className="stat-value">{stats.total}</div>
              <div className="stat-label">Total Documents</div>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon success"><HiOutlineShieldCheck /></div>
            <div className="stat-content">
              <div className="stat-value">{stats.verified}</div>
              <div className="stat-label">Verified</div>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon warning"><HiOutlineClock /></div>
            <div className="stat-content">
              <div className="stat-value">{stats.pending_review}</div>
              <div className="stat-label">Pending Review</div>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon danger"><HiOutlineXCircle /></div>
            <div className="stat-content">
              <div className="stat-value">{stats.rejected}</div>
              <div className="stat-label">Rejected</div>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon info"><HiOutlineChartBar /></div>
            <div className="stat-content">
              <div className="stat-value">{stats.avg_confidence}%</div>
              <div className="stat-label">Avg. Confidence</div>
            </div>
          </div>
        </div>

        {/* By Doc Type */}
        {Object.keys(stats.by_doc_type).length > 0 && (
          <div className="card fade-in" style={{ marginBottom: '20px' }}>
            <div className="card-header"><h3 className="card-title">Documents by Type</h3></div>
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              {Object.entries(stats.by_doc_type).map(([type, count]) => (
                <div key={type} className="score-item" style={{ flex: '1', minWidth: '140px' }}>
                  <span className="score-item-label">{DOC_TYPE_LABELS[type] || type}</span>
                  <span className="score-item-value">{count}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recent Documents */}
        <div className="card fade-in">
          <div className="card-header">
            <h3 className="card-title">Recent Documents</h3>
            <button className="btn btn-secondary btn-sm" onClick={() => navigate('/documents')}>View All</button>
          </div>
          {stats.recent_uploads.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📄</div>
              <div className="empty-state-title">No documents yet</div>
              <p>Upload your first document to get started.</p>
            </div>
          ) : (
            <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Confidence</th>
                  <th>Uploaded</th>
                </tr>
              </thead>
              <tbody>
                {stats.recent_uploads.map((doc) => (
                  <tr key={doc.doc_id} onClick={() => navigate(`/result/${doc.doc_id}`)}>
                    <td style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                      {doc.original_filename || doc.doc_id.slice(0, 8) + '...'}
                    </td>
                    <td>{DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type}</td>
                    <td><span className={`status-badge ${getStatusClass(doc.status)}`}>{doc.status}</span></td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                      {doc.confidence_score != null ? `${doc.confidence_score}%` : '—'}
                    </td>
                    <td>{timeAgo(doc.created_at)}</td>
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
