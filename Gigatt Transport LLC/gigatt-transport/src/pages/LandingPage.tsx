import React from 'react';
import { Link } from 'react-router-dom';
import PublicNav from '../components/PublicNav';
import {
  ArrowRight,
  Radio,
  MapPin,
  Shield,
  FileCheck,
  Zap,
  ChevronRight,
  Phone,
  Mail,
} from 'lucide-react';

const STATES = ['TX', 'AR', 'OK', 'LA', 'NM', 'KS', 'MO'];

const SERVICES = [
  {
    icon: Radio,
    title: 'High-Pole Escort',
    subtitle: 'Certified Operators',
    desc: 'Licensed high-pole and flag-vehicle escort for oversize loads. Trained operators with defensive driving certifications and full insurance coverage.',
  },
  {
    icon: ArrowRight,
    title: 'Pilot / Chase',
    subtitle: 'Front & Rear',
    desc: 'Dedicated front pilot and rear chase vehicles for wide or long loads. Coordinated communication through every mile of the move.',
  },
  {
    icon: MapPin,
    title: 'Route Planning',
    subtitle: 'Permit-Friendly',
    desc: 'Pre-planned routes optimized for oversize clearance, low bridges, and permit restrictions. Documented and reproducible.',
  },
  {
    icon: FileCheck,
    title: 'Compliance-Ready',
    subtitle: 'PEVO / WITPAC Aware',
    desc: 'Operations conducted with awareness of PEVO and WITPAC protocols. Insurance on file. Clean operational history.',
  },
];

const CRED_ITEMS = [
  { icon: Shield, label: 'Fully Insured Operations' },
  { icon: Zap, label: 'PEVO / WITPAC Aware' },
  { icon: FileCheck, label: 'Permit-Friendly Routing' },
  { icon: MapPin, label: 'Documented Route History' },
];

const LandingPage: React.FC = () => {
  return (
    <div className="min-h-screen" style={{ background: 'var(--color-bg)' }}>
      <PublicNav />

      {/* ── HERO ─────────────────────────────────────────────── */}
      <section
        className="relative min-h-screen flex items-center overflow-hidden"
        style={{
          background: `
            radial-gradient(ellipse 80% 60% at 60% 40%, rgba(244,167,21,0.07) 0%, transparent 70%),
            linear-gradient(180deg, #0a0c0f 0%, #0d1018 100%)
          `,
        }}
      >
        {/* Grid pattern overlay */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage: `
              linear-gradient(rgba(244,167,21,0.04) 1px, transparent 1px),
              linear-gradient(90deg, rgba(244,167,21,0.04) 1px, transparent 1px)
            `,
            backgroundSize: '60px 60px',
          }}
        />

        {/* Large BG text */}
        <div
          className="absolute right-0 top-1/2 -translate-y-1/2 display-font select-none pointer-events-none"
          style={{
            fontSize: 'clamp(8rem, 22vw, 22rem)',
            color: 'rgba(244,167,21,0.03)',
            lineHeight: 1,
            letterSpacing: '-0.02em',
          }}
        >
          OVR
        </div>

        <div className="relative z-10 max-w-6xl mx-auto px-6 pt-24 pb-20">
          <div className="max-w-3xl">
            {/* Label */}
            <div className="anim-fade-up flex items-center gap-3 mb-6">
              <span className="accent-line" />
              <span className="mono-font text-xs tracking-widest" style={{ color: 'var(--color-accent)' }}>
                OVERSIZE / OVERWEIGHT TRANSPORT SUPPORT
              </span>
            </div>

            {/* Headline */}
            <h1
              className="anim-fade-up-delay-1 display-font mb-6 leading-none"
              style={{ fontSize: 'clamp(3.5rem, 10vw, 8rem)', color: 'var(--color-text)' }}
            >
              MOVE BIG.
              <br />
              <span style={{ color: 'var(--color-accent)' }}>MOVE RIGHT.</span>
            </h1>

            <p
              className="anim-fade-up-delay-2 text-lg mb-10 max-w-xl leading-relaxed"
              style={{ color: 'var(--color-muted)' }}
            >
              Gigatt Transport LLC provides certified high-pole escort, front pilot,
              rear chase, and permit-friendly route planning for oversize and overweight loads
              across Texas, Arkansas, Oklahoma, and beyond.
            </p>

            <div className="anim-fade-up-delay-3 flex flex-col sm:flex-row gap-4">
              <Link to="/request">
                <button className="btn-primary flex items-center gap-2 text-base">
                  REQUEST A ROUTE / JOB
                  <ArrowRight size={16} />
                </button>
              </Link>
              <a
                href="#services"
                className="flex items-center gap-2 px-6 py-3 text-sm border border-opacity-30 rounded transition-colors hover:border-opacity-60"
                style={{
                  borderColor: 'var(--color-border)',
                  color: 'var(--color-muted)',
                }}
              >
                OUR SERVICES
                <ChevronRight size={14} />
              </a>
            </div>

            {/* State chips */}
            <div className="anim-fade-up-delay-4 flex flex-wrap gap-2 mt-10">
              {STATES.map(s => (
                <span
                  key={s}
                  className="mono-font text-xs px-3 py-1.5 rounded"
                  style={{
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    color: 'var(--color-muted)',
                  }}
                >
                  {s}
                </span>
              ))}
              <span
                className="mono-font text-xs px-3 py-1.5 rounded"
                style={{
                  background: 'rgba(244,167,21,0.08)',
                  border: '1px solid rgba(244,167,21,0.2)',
                  color: 'var(--color-accent)',
                }}
              >
                + MORE
              </span>
            </div>
          </div>
        </div>

        {/* Bottom fade */}
        <div
          className="absolute bottom-0 left-0 right-0 h-32 pointer-events-none"
          style={{ background: 'linear-gradient(transparent, var(--color-bg))' }}
        />
      </section>

      {/* ── CREDIBILITY STRIP ───────────────────────────────── */}
      <section
        style={{
          borderTop: '1px solid var(--color-border)',
          borderBottom: '1px solid var(--color-border)',
          background: 'var(--color-surface)',
        }}
      >
        <div className="max-w-6xl mx-auto px-6 py-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {CRED_ITEMS.map(({ icon: Icon, label }) => (
              <div key={label} className="flex items-center gap-3">
                <Icon size={16} style={{ color: 'var(--color-accent)', flexShrink: 0 }} />
                <span className="text-sm" style={{ color: 'var(--color-muted)' }}>
                  {label}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── SERVICES ────────────────────────────────────────── */}
      <section id="services" className="py-24">
        <div className="max-w-6xl mx-auto px-6">
          <div className="mb-14">
            <div className="flex items-center gap-3 mb-4">
              <span className="accent-line" />
              <span className="mono-font text-xs tracking-widest" style={{ color: 'var(--color-accent)' }}>
                WHAT WE DO
              </span>
            </div>
            <h2 className="display-font text-5xl md:text-6xl" style={{ color: 'var(--color-text)' }}>
              SERVICES
            </h2>
          </div>

          <div className="grid md:grid-cols-2 gap-5">
            {SERVICES.map(({ icon: Icon, title, subtitle, desc }) => (
              <div
                key={title}
                className="group p-7 rounded-lg transition-all duration-300 hover:border-opacity-60"
                style={{
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLElement).style.borderColor = 'rgba(244,167,21,0.3)';
                  (e.currentTarget as HTMLElement).style.background = 'var(--color-surface-2)';
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLElement).style.borderColor = 'var(--color-border)';
                  (e.currentTarget as HTMLElement).style.background = 'var(--color-surface)';
                }}
              >
                <div className="flex items-start gap-4">
                  <div
                    className="flex-shrink-0 w-10 h-10 rounded flex items-center justify-center"
                    style={{ background: 'rgba(244,167,21,0.1)' }}
                  >
                    <Icon size={18} style={{ color: 'var(--color-accent)' }} />
                  </div>
                  <div>
                    <div className="flex items-baseline gap-2 mb-1">
                      <span className="display-font text-xl" style={{ color: 'var(--color-text)' }}>
                        {title}
                      </span>
                      <span className="mono-font text-xs" style={{ color: 'var(--color-accent)' }}>
                        / {subtitle}
                      </span>
                    </div>
                    <p className="text-sm leading-relaxed" style={{ color: 'var(--color-muted)' }}>
                      {desc}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── GEOGRAPHIC COVERAGE ─────────────────────────────── */}
      <section
        id="coverage"
        className="py-24"
        style={{ background: 'var(--color-surface)' }}
      >
        <div className="max-w-6xl mx-auto px-6">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div>
              <div className="flex items-center gap-3 mb-4">
                <span className="accent-line" />
                <span className="mono-font text-xs tracking-widest" style={{ color: 'var(--color-accent)' }}>
                  COVERAGE AREA
                </span>
              </div>
              <h2 className="display-font text-5xl md:text-6xl mb-6" style={{ color: 'var(--color-text)' }}>
                PRIMARY<br />STATES
              </h2>
              <p className="text-base leading-relaxed mb-8" style={{ color: 'var(--color-muted)' }}>
                Primary operations in Texas and Arkansas, with active coverage
                across Oklahoma, Louisiana, and surrounding states. Multi-state
                moves handled with permit-aware routing and proper escort coordination.
              </p>
              <div className="flex flex-wrap gap-2">
                {STATES.map(s => (
                  <span
                    key={s}
                    className="mono-font text-sm font-medium px-4 py-2 rounded"
                    style={{
                      background: 'var(--color-surface-2)',
                      border: '1px solid var(--color-border)',
                      color: 'var(--color-text)',
                    }}
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>

            <div
              className="rounded-lg p-8"
              style={{
                background: 'var(--color-surface-2)',
                border: '1px solid var(--color-border)',
              }}
            >
              <div className="mb-6">
                <span className="mono-font text-xs tracking-wider" style={{ color: 'var(--color-accent)' }}>
                  OPERATIONAL STRENGTHS
                </span>
              </div>
              <ul className="space-y-4">
                {[
                  'TX–AR corridor: primary focus, highest route frequency',
                  'OK–AR cross-state moves with single-day turnaround',
                  'Multi-state permit coordination assistance',
                  'Pre-scouted route segments on common corridors',
                  'Available for early morning dispatch, weekends considered',
                ].map(item => (
                  <li key={item} className="flex items-start gap-3">
                    <span style={{ color: 'var(--color-accent)', flexShrink: 0 }}>▸</span>
                    <span className="text-sm" style={{ color: 'var(--color-muted)' }}>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA ─────────────────────────────────────────────── */}
      <section className="py-24 relative overflow-hidden">
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: 'radial-gradient(ellipse 60% 80% at 50% 50%, rgba(244,167,21,0.06) 0%, transparent 70%)',
          }}
        />
        <div className="relative z-10 max-w-3xl mx-auto px-6 text-center">
          <h2 className="display-font text-5xl md:text-7xl mb-6" style={{ color: 'var(--color-text)' }}>
            READY TO<br /><span style={{ color: 'var(--color-accent)' }}>MOVE?</span>
          </h2>
          <p className="text-base mb-10" style={{ color: 'var(--color-muted)' }}>
            Submit your route or job request and we'll review it and get back to you within one business day.
          </p>
          <Link to="/request">
            <button className="btn-primary text-base flex items-center gap-2 mx-auto">
              REQUEST A ROUTE / JOB
              <ArrowRight size={16} />
            </button>
          </Link>
        </div>
      </section>

      {/* ── FOOTER ──────────────────────────────────────────── */}
      <footer
        id="contact"
        style={{
          borderTop: '1px solid var(--color-border)',
          background: 'var(--color-surface)',
        }}
      >
        <div className="max-w-6xl mx-auto px-6 py-12 grid md:grid-cols-3 gap-10">
          <div>
            <div className="display-font text-2xl mb-2" style={{ color: 'var(--color-accent)' }}>
              GIGATT TRANSPORT LLC
            </div>
            <p className="text-sm" style={{ color: 'var(--color-muted)' }}>
              Oversize &amp; overweight escort operations.<br />Oklahoma-based. Multi-state capable.
            </p>
          </div>
          <div>
            <div className="mono-font text-xs tracking-widest mb-4" style={{ color: 'var(--color-accent)' }}>
              CONTACT
            </div>
            <div className="space-y-2">
              {/* TODO: Replace with real contact info */}
              <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--color-muted)' }}>
                <Phone size={14} />
                <span>(xxx) xxx-xxxx</span>
              </div>
              <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--color-muted)' }}>
                <Mail size={14} />
                <span>contact@gigatttransport.com</span>
              </div>
            </div>
          </div>
          <div>
            <div className="mono-font text-xs tracking-widest mb-4" style={{ color: 'var(--color-accent)' }}>
              QUICK LINKS
            </div>
            <div className="space-y-2">
              <Link to="/request" className="block text-sm hover:text-white transition-colors" style={{ color: 'var(--color-muted)' }}>
                Request a Route / Job
              </Link>
              <a href="#services" className="block text-sm hover:text-white transition-colors" style={{ color: 'var(--color-muted)' }}>
                Services
              </a>
            </div>
          </div>
        </div>
        <div
          className="max-w-6xl mx-auto px-6 py-4 flex justify-between items-center"
          style={{ borderTop: '1px solid var(--color-border)' }}
        >
          <span className="mono-font text-xs" style={{ color: 'var(--color-muted)' }}>
            © 2025 Gigatt Transport LLC. All rights reserved.
          </span>
          <Link to="/admin/login" className="mono-font text-xs" style={{ color: 'var(--color-border)' }}>
            admin
          </Link>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
