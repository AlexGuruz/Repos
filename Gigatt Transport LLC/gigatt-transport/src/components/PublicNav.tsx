import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Menu, X } from 'lucide-react';

const PublicNav: React.FC = () => {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 40);
    window.addEventListener('scroll', handler);
    return () => window.removeEventListener('scroll', handler);
  }, []);

  useEffect(() => setMenuOpen(false), [location]);

  return (
    <nav
      className="fixed top-0 left-0 right-0 z-50 transition-all duration-300"
      style={{
        background: scrolled ? 'rgba(10,12,15,0.95)' : 'transparent',
        backdropFilter: scrolled ? 'blur(12px)' : 'none',
        borderBottom: scrolled ? '1px solid var(--color-border)' : '1px solid transparent',
      }}
    >
      <div className="max-w-6xl mx-auto px-6 flex items-center justify-between h-16">
        <Link to="/" className="flex items-center gap-2">
          <span className="display-font text-2xl" style={{ color: 'var(--color-accent)' }}>
            GIGATT
          </span>
          <span className="mono-font text-xs" style={{ color: 'var(--color-muted)', marginTop: '2px' }}>
            TRANSPORT
          </span>
        </Link>

        {/* Desktop nav */}
        <div className="hidden md:flex items-center gap-8">
          <a
            href="#services"
            className="text-sm transition-colors hover:text-white"
            style={{ color: 'var(--color-muted)' }}
          >
            Services
          </a>
          <a
            href="#coverage"
            className="text-sm transition-colors hover:text-white"
            style={{ color: 'var(--color-muted)' }}
          >
            Coverage
          </a>
          <a
            href="#contact"
            className="text-sm transition-colors hover:text-white"
            style={{ color: 'var(--color-muted)' }}
          >
            Contact
          </a>
          <Link to="/request">
            <button className="btn-primary text-sm py-2 px-5">
              REQUEST A ROUTE
            </button>
          </Link>
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden p-2"
          style={{ color: 'var(--color-muted)' }}
          onClick={() => setMenuOpen(!menuOpen)}
        >
          {menuOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <div
          className="md:hidden px-6 pb-6 flex flex-col gap-5"
          style={{ background: 'rgba(10,12,15,0.98)', borderTop: '1px solid var(--color-border)' }}
        >
          <a href="#services" className="text-sm pt-4" style={{ color: 'var(--color-muted)' }}>Services</a>
          <a href="#coverage" className="text-sm" style={{ color: 'var(--color-muted)' }}>Coverage</a>
          <a href="#contact" className="text-sm" style={{ color: 'var(--color-muted)' }}>Contact</a>
          <Link to="/request">
            <button className="btn-primary w-full text-sm">REQUEST A ROUTE</button>
          </Link>
        </div>
      )}
    </nav>
  );
};

export default PublicNav;
