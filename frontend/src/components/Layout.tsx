import { NavLink, Outlet } from 'react-router-dom';
import {
  HiOutlineHome, HiOutlineDocumentText, HiOutlineUpload,
  HiOutlineClipboardCheck, HiOutlineShieldCheck,
  HiOutlineIdentification, HiOutlineCreditCard,
  HiOutlineAcademicCap, HiOutlineBriefcase,
  HiOutlineDocumentDuplicate, HiOutlineLogout,
  HiOutlineMenu, HiOutlineX,
} from 'react-icons/hi';
import { useState, useEffect } from 'react';
import { getQueue } from '../api';

export default function Layout() {
  const [queueCount, setQueueCount] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const user = localStorage.getItem('docverify_user') || 'HR Admin';

  useEffect(() => {
    getQueue().then(q => setQueueCount(q.length)).catch(() => {});
    const interval = setInterval(() => {
      getQueue().then(q => setQueueCount(q.length)).catch(() => {});
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (menuOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [menuOpen]);

  const handleLogout = () => {
    localStorage.removeItem('docverify_user');
    localStorage.removeItem('docverify_api_key');
    window.location.href = '/login';
  };

  const closeMenu = () => setMenuOpen(false);

  return (
    <div className="app-layout">
      <div
        className={`sidebar-overlay ${menuOpen ? 'visible' : ''}`}
        onClick={closeMenu}
        aria-hidden="true"
      />

      <aside className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <div className="sidebar-logo-icon">DV</div>
            <span className="sidebar-logo-text">DocVerify AI</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section-label">Main</div>
          <NavLink to="/" end className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`} onClick={closeMenu}>
            <span className="nav-item-icon"><HiOutlineHome /></span>
            Dashboard
          </NavLink>
          <NavLink to="/upload" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`} onClick={closeMenu}>
            <span className="nav-item-icon"><HiOutlineUpload /></span>
            Upload
          </NavLink>
          <NavLink to="/documents" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`} onClick={closeMenu}>
            <span className="nav-item-icon"><HiOutlineDocumentText /></span>
            All Documents
          </NavLink>
          <NavLink to="/review" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`} onClick={closeMenu}>
            <span className="nav-item-icon"><HiOutlineClipboardCheck /></span>
            Review Queue
            {queueCount > 0 && <span className="nav-item-badge">{queueCount}</span>}
          </NavLink>

          <div className="nav-section-label">Document Types</div>
          <NavLink to="/verify/aadhaar" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`} onClick={closeMenu}>
            <span className="nav-item-icon"><HiOutlineIdentification /></span>
            Aadhaar Card
          </NavLink>
          <NavLink to="/verify/pan" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`} onClick={closeMenu}>
            <span className="nav-item-icon"><HiOutlineCreditCard /></span>
            PAN Card
          </NavLink>
          <NavLink to="/verify/education" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`} onClick={closeMenu}>
            <span className="nav-item-icon"><HiOutlineAcademicCap /></span>
            Education
          </NavLink>
          <NavLink to="/verify/experience" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`} onClick={closeMenu}>
            <span className="nav-item-icon"><HiOutlineBriefcase /></span>
            Experience
          </NavLink>
          <NavLink to="/verify/caste" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`} onClick={closeMenu}>
            <span className="nav-item-icon"><HiOutlineShieldCheck /></span>
            Caste Certificate
          </NavLink>
          <NavLink to="/verify/resume" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`} onClick={closeMenu}>
            <span className="nav-item-icon"><HiOutlineDocumentDuplicate /></span>
            Resume / CV
          </NavLink>
          <NavLink to="/verify/general" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`} onClick={closeMenu}>
            <span className="nav-item-icon"><HiOutlineDocumentText /></span>
            General
          </NavLink>
        </nav>

        <div style={{ padding: '14px', borderTop: '1px solid var(--border-secondary)' }}>
          <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginBottom: '8px' }}>
            Signed in as <strong style={{ color: 'var(--text-secondary)' }}>{user}</strong>
          </div>
          <button className="nav-item" onClick={handleLogout} style={{ width: '100%' }}>
            <span className="nav-item-icon"><HiOutlineLogout /></span>
            Sign Out
          </button>
        </div>
      </aside>

      <div className="main-content">
        <header className="mobile-top-bar">
          <button
            type="button"
            className="mobile-menu-btn"
            onClick={() => setMenuOpen(o => !o)}
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          >
            {menuOpen ? <HiOutlineX /> : <HiOutlineMenu />}
          </button>
          <span style={{ fontWeight: 700, fontSize: '16px', color: 'var(--text-primary)' }}>DocVerify AI</span>
          <div style={{ width: 44 }} />
        </header>

        <Outlet />

        <nav className="mobile-bottom-nav">
          <NavLink to="/" end className={({isActive}) => isActive ? 'active' : ''}>
            <HiOutlineHome size={22} />
            Home
          </NavLink>
          <NavLink to="/upload" className={({isActive}) => isActive ? 'active' : ''}>
            <HiOutlineUpload size={22} />
            Upload
          </NavLink>
          <NavLink to="/review" className={({isActive}) => isActive ? 'active' : ''}>
            <HiOutlineClipboardCheck size={22} />
            Review
          </NavLink>
          <NavLink to="/documents" className={({isActive}) => isActive ? 'active' : ''}>
            <HiOutlineDocumentText size={22} />
            Docs
          </NavLink>
        </nav>
      </div>
    </div>
  );
}
