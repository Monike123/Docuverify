import { useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { healthCheck } from '../api';

const VALID_USERS: Record<string, string> = {
  'admin': 'docverify2024',
  'hr.executive': 'hr@verify123',
  'hr.manager': 'manager@verify',
};

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    // Simple auth (replace with Supabase Auth in production)
    if (VALID_USERS[username] === password) {
      localStorage.setItem('docverify_user', username);

      // Test backend connection
      try {
        await healthCheck();
      } catch {
        // Backend might not be running yet, proceed anyway
      }

      navigate('/');
    } else {
      setError('Invalid credentials. Contact your HR administrator.');
    }
    setLoading(false);
  };

  return (
    <div className="login-page">
      <div className="login-card fade-in">
        <div className="login-logo">
          <div className="login-logo-icon pulse-glow">DV</div>
          <h1 className="login-title">DocVerify AI</h1>
          <p className="login-subtitle">HR Document Verification Platform</p>
        </div>

        {error && <div className="login-error">{error}</div>}

        <form onSubmit={handleLogin}>
          <div className="form-group">
            <label className="form-label">Username</label>
            <input
              className="form-input"
              type="text"
              placeholder="e.g., hr.executive"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label className="form-label">Password</label>
            <input
              className="form-input"
              type="password"
              placeholder="Enter password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-lg"
            style={{ width: '100%', justifyContent: 'center', marginTop: '8px' }}
            disabled={loading}
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div style={{ marginTop: '20px', textAlign: 'center', fontSize: '12px', color: 'var(--text-muted)' }}>
          Internal use only • Authorized personnel
        </div>
      </div>
    </div>
  );
}
