import { useNavigate } from 'react-router-dom';
import {
  HiOutlineIdentification, HiOutlineCreditCard, HiOutlineAcademicCap,
  HiOutlineBriefcase, HiOutlineShieldCheck, HiOutlineDocumentDuplicate,
  HiOutlineDocumentText,
} from 'react-icons/hi';

const DOC_TYPES = [
  { key: 'aadhaar', title: 'Aadhaar Card', desc: 'Identity verification with UID, name, DOB', icon: <HiOutlineIdentification />, color: 'var(--color-aadhaar)' },
  { key: 'pan', title: 'PAN Card', desc: 'Tax ID format validation & extraction', icon: <HiOutlineCreditCard />, color: 'var(--color-pan)' },
  { key: 'education', title: 'Education Certificate', desc: 'Degree, marksheet, diploma verification', icon: <HiOutlineAcademicCap />, color: 'var(--color-education)' },
  { key: 'experience', title: 'Experience Letter', desc: 'Employment verification with letterhead check', icon: <HiOutlineBriefcase />, color: 'var(--color-experience)' },
  { key: 'caste', title: 'Caste Certificate', desc: 'Community certificate extraction', icon: <HiOutlineShieldCheck />, color: 'var(--color-caste)' },
  { key: 'resume', title: 'Resume / CV', desc: 'Extract sections, skills, contact info', icon: <HiOutlineDocumentDuplicate />, color: 'var(--color-resume)' },
  { key: 'general', title: 'General Document', desc: 'Any document — auto key-value extraction', icon: <HiOutlineDocumentText />, color: 'var(--color-general)' },
];

export default function UploadPage() {
  const navigate = useNavigate();

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Upload Document</h1>
          <p className="page-subtitle">Select document type to start verification</p>
        </div>
      </div>

      <div className="page-body">
        <div className="doc-type-grid fade-in">
          {DOC_TYPES.map(dt => (
            <div
              key={dt.key}
              className="doc-type-card"
              onClick={() => navigate(`/verify/${dt.key}`)}
            >
              <div className="doc-type-card-icon" style={{ background: `${dt.color}15`, color: dt.color }}>
                {dt.icon}
              </div>
              <div className="doc-type-card-title">{dt.title}</div>
              <div className="doc-type-card-desc">{dt.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
