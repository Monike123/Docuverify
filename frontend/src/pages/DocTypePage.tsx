import { useState, useRef } from 'react';
import type { DragEvent } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { HiOutlineUpload, HiOutlineDocumentSearch, HiOutlineX } from 'react-icons/hi';
import { uploadDocument, analyzeDocument } from '../api';

const IMAGE_ACCEPT = '.jpg,.jpeg,.png,.pdf';

const DOC_INFO: Record<string, { title: string; desc: string; icon: string; accept: string }> = {
  aadhaar: { title: 'Aadhaar Card', desc: 'Upload Aadhaar card image or PDF for identity verification. Extracts UID, name, DOB, address, and masks PII.', icon: '🪪', accept: IMAGE_ACCEPT },
  pan: { title: 'PAN Card', desc: 'Upload PAN card for tax ID verification. Validates PAN format, extracts name and number, and masks sensitive data.', icon: '💳', accept: IMAGE_ACCEPT },
  caste: { title: 'Caste Certificate', desc: 'Upload caste or community certificate (JPG, PNG, or PDF). Extracts applicant name, category, issuing authority, and certificate number.', icon: '📜', accept: IMAGE_ACCEPT },
  experience: { title: 'Experience Letter', desc: 'Upload experience or employment letter (JPG, PNG, or PDF). Extracts company, employee name, dates, designation, and detects letterhead.', icon: '📋', accept: IMAGE_ACCEPT },
  education: { title: 'Education Certificate', desc: 'Upload degree, diploma, or marksheet (JPG, PNG, or PDF). Extracts institution, degree, CGPA/percentage, passing year, and registration number.', icon: '🎓', accept: IMAGE_ACCEPT },
  resume: { title: 'Resume / CV', desc: 'Upload resume or CV as JPG, PNG, or PDF. Extracts contact info, education, experience, skills, and projects sections.', icon: '📄', accept: IMAGE_ACCEPT },
  general: { title: 'General Document', desc: 'Upload any document for OCR extraction (JPG, PNG, or PDF). Detects key-value pairs, dates, emails, and phone numbers.', icon: '📎', accept: IMAGE_ACCEPT },
};

export default function DocTypePage() {
  const { docType = 'general' } = useParams();
  const navigate = useNavigate();
  const fileRef = useRef<HTMLInputElement>(null);
  const info = DOC_INFO[docType] || DOC_INFO.general;

  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [status, setStatus] = useState<'idle' | 'uploading' | 'analyzing' | 'done' | 'error'>('idle');
  const [progress, setProgress] = useState('');
  const [error, setError] = useState('');

  const handleFile = (f: File) => {
    setFile(f);
    setError('');
    if (f.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = () => setPreview(reader.result as string);
      reader.readAsDataURL(f);
    } else {
      setPreview(null);
    }
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length > 0) handleFile(e.dataTransfer.files[0]);
  };

  const handleAnalyze = async () => {
    if (!file) return;
    setStatus('uploading');
    setProgress('Uploading document...');
    setError('');

    try {
      const { doc_id } = await uploadDocument(file, docType);
      setStatus('analyzing');
      setProgress('Running OCR & verification pipeline...');
      await analyzeDocument(doc_id);
      setStatus('done');
      navigate(`/result/${doc_id}`);
    } catch (err: any) {
      setStatus('error');
      setError(err?.response?.data?.detail || err.message || 'Analysis failed');
    }
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">{info.icon} {info.title} Verification</h1>
          <p className="page-subtitle">{info.desc}</p>
        </div>
      </div>

      <div className="page-body">
        <div style={{ maxWidth: '720px', margin: '0 auto' }}>
          {/* Upload Zone */}
          <div
            className={`upload-zone fade-in ${dragOver ? 'drag-over' : ''}`}
            onClick={() => fileRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
          >
            <input
              ref={fileRef}
              type="file"
              accept={info.accept}
              onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
              style={{ display: 'none' }}
            />
            <div className="upload-zone-icon"><HiOutlineUpload /></div>
            <div className="upload-zone-title">
              {file ? file.name : 'Drop your file here or click to browse'}
            </div>
            <div className="upload-zone-subtitle">
              JPG, PNG, or PDF only • Max 10MB
            </div>
          </div>

          {/* Preview */}
          {preview && (
            <div className="card fade-in" style={{ marginTop: '16px' }}>
              <div className="card-header">
                <h3 className="card-title">Preview</h3>
                <button className="btn btn-secondary btn-sm" onClick={() => { setFile(null); setPreview(null); }}>
                  <HiOutlineX /> Remove
                </button>
              </div>
              <div className="image-viewer">
                <img src={preview} alt="Preview" style={{ maxHeight: '400px', objectFit: 'contain' }} />
              </div>
            </div>
          )}

          {/* File info for non-image */}
          {file && !preview && (
            <div className="card fade-in" style={{ marginTop: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{file.name}</div>
                  <div style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>
                    {(file.size / 1024).toFixed(1)} KB • {file.type || 'document'}
                  </div>
                </div>
                <button className="btn btn-secondary btn-sm" onClick={() => setFile(null)}>
                  <HiOutlineX /> Remove
                </button>
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="login-error fade-in" style={{ marginTop: '16px' }}>{error}</div>
          )}

          {/* Actions */}
          <div style={{ marginTop: '20px', display: 'flex', gap: '12px' }}>
            <button
              className="btn btn-primary btn-lg"
              style={{ flex: 1, justifyContent: 'center' }}
              disabled={!file || status === 'uploading' || status === 'analyzing'}
              onClick={handleAnalyze}
            >
              {status === 'uploading' || status === 'analyzing' ? (
                <>
                  <div className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
                  {progress}
                </>
              ) : (
                <>
                  <HiOutlineDocumentSearch /> Verify & Extract
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
