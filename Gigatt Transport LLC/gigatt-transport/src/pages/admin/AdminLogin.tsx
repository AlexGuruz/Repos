import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Truck, AlertCircle } from 'lucide-react';
import { useApp } from '../../context/AppContext';

const AdminLogin: React.FC = () => {
  const { login } = useApp();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    // TODO: Replace with real API auth call
    await new Promise(res => setTimeout(res, 500));
    const ok = login(username, password);

    if (ok) {
      navigate('/admin/requests');
    } else {
      setError('Invalid credentials');
    }
    setLoading(false);
  };

  return (
    <div
      className="admin-body min-h-screen flex items-center justify-center px-4"
      style={{ background: '#f4f5f7' }}
    >
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div
            className="inline-flex items-center justify-center w-12 h-12 rounded-lg mb-3"
            style={{ background: '#1a3a5c' }}
          >
            <Truck size={22} style={{ color: '#f4a715' }} />
          </div>
          <h1 className="text-xl font-bold" style={{ color: '#1a1d23' }}>
            Gigatt Transport
          </h1>
          <p className="text-sm mt-1" style={{ color: '#6b7280' }}>
            Admin Portal
          </p>
        </div>

        <div className="admin-card p-8">
          <h2 className="text-base font-semibold mb-6" style={{ color: '#1a1d23' }}>
            Sign In
          </h2>

          {error && (
            <div
              className="flex items-center gap-2 p-3 rounded mb-5 text-sm"
              style={{ background: '#fee2e2', color: '#991b1b' }}
            >
              <AlertCircle size={14} />
              {error}
            </div>
          )}

          {/* Demo hint */}
          <div
            className="text-xs p-3 rounded mb-5 font-mono"
            style={{ background: '#f0f4ff', color: '#6b7280', border: '1px solid #e2e8ff' }}
          >
            Demo: admin / gigatt
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#374151' }}>
                Username
              </label>
              <input
                className="admin-input"
                type="text"
                placeholder="admin"
                value={username}
                onChange={e => setUsername(e.target.value)}
                autoComplete="username"
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#374151' }}>
                Password
              </label>
              <input
                className="admin-input"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={e => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>

            <button
              type="submit"
              disabled={loading || !username || !password}
              className="w-full py-2.5 px-4 rounded text-sm font-medium text-white transition-all mt-2"
              style={{
                background: loading || !username || !password ? '#94a3b8' : '#1a3a5c',
                cursor: loading || !username || !password ? 'not-allowed' : 'pointer',
              }}
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default AdminLogin;
