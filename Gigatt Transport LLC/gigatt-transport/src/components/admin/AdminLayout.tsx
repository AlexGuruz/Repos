import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { LayoutList, LogOut, Truck } from 'lucide-react';
import { useApp } from '../../context/AppContext';

interface Props {
  children: React.ReactNode;
}

const AdminLayout: React.FC<Props> = ({ children }) => {
  const { auth, logout } = useApp();
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/admin/login');
  };

  const navItems = [
    { path: '/admin/requests', label: 'Requests', icon: LayoutList },
  ];

  return (
    <div className="admin-body min-h-screen flex">
      {/* Sidebar */}
      <aside
        className="w-56 flex-shrink-0 flex flex-col"
        style={{
          background: '#1a3a5c',
          color: '#fff',
          minHeight: '100vh',
          position: 'sticky',
          top: 0,
        }}
      >
        {/* Logo */}
        <div
          className="px-5 py-5 flex items-center gap-2"
          style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}
        >
          <Truck size={18} style={{ color: '#f4a715' }} />
          <div>
            <div className="font-bold text-sm tracking-wide">GIGATT</div>
            <div className="text-xs opacity-50 font-mono">ADMIN</div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 px-3 space-y-1">
          {navItems.map(({ path, label, icon: Icon }) => {
            const active = location.pathname.startsWith(path);
            return (
              <Link
                key={path}
                to={path}
                className="flex items-center gap-3 px-3 py-2.5 rounded text-sm transition-all"
                style={{
                  background: active ? 'rgba(244,167,21,0.15)' : 'transparent',
                  color: active ? '#f4a715' : 'rgba(255,255,255,0.6)',
                  fontWeight: active ? 500 : 400,
                }}
              >
                <Icon size={15} />
                {label}
              </Link>
            );
          })}
        </nav>

        {/* User / logout */}
        <div
          className="px-4 py-4"
          style={{ borderTop: '1px solid rgba(255,255,255,0.1)' }}
        >
          <div className="text-xs opacity-40 mb-2 font-mono">{auth.username}</div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-sm opacity-60 hover:opacity-100 transition-opacity"
          >
            <LogOut size={14} />
            Log out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 min-w-0">
        {children}
      </main>
    </div>
  );
};

export default AdminLayout;
