import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import PublicNav from '../components/PublicNav';
import { ArrowLeft, CheckCircle } from 'lucide-react';
import { STATES, SERVICE_TYPES } from '../data/mockData';

// ── Types ────────────────────────────────────────────────────
interface FormData {
  name: string;
  company: string;
  email: string;
  phone: string;
  origin: string;
  destination: string;
  dateWindow: string;
  loadDescription: string;
  height: string;
  width: string;
  length: string;
  weight: string;
  statesInvolved: string[];
  serviceTypes: string[];
  additionalNotes: string;
}

interface Errors {
  [key: string]: string;
}

const INITIAL_FORM: FormData = {
  name: '', company: '', email: '', phone: '',
  origin: '', destination: '', dateWindow: '',
  loadDescription: '', height: '', width: '', length: '', weight: '',
  statesInvolved: [], serviceTypes: [], additionalNotes: '',
};

// ── Validation ──────────────────────────────────────────────
const validate = (data: FormData): Errors => {
  const errs: Errors = {};
  if (!data.name.trim()) errs.name = 'Name is required';
  if (!data.email.trim()) {
    errs.email = 'Email is required';
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) {
    errs.email = 'Enter a valid email address';
  }
  if (data.phone && !/^[\d\s\-().+]{7,}$/.test(data.phone)) {
    errs.phone = 'Enter a valid phone number';
  }
  if (!data.origin.trim()) errs.origin = 'Origin is required';
  if (!data.destination.trim()) errs.destination = 'Destination is required';
  if (!data.loadDescription.trim()) errs.loadDescription = 'Load description is required';
  if (data.serviceTypes.length === 0) errs.serviceTypes = 'Select at least one service type';
  return errs;
};

// ── Field helpers ───────────────────────────────────────────
const Field = ({
  label, required, error, children,
}: {
  label: string; required?: boolean; error?: string; children: React.ReactNode;
}) => (
  <div>
    <label className="field-label">
      {label}{required && <span style={{ color: 'var(--color-accent)' }}> *</span>}
    </label>
    {children}
    {error && <p className="field-error">{error}</p>}
  </div>
);

// ── Sub-sections ─────────────────────────────────────────────
const ContactSection = ({
  data, errors, onChange,
}: {
  data: FormData; errors: Errors; onChange: (field: keyof FormData, val: string) => void;
}) => (
  <div>
    <SectionHeader label="01" title="CONTACT INFO" />
    <div className="grid md:grid-cols-2 gap-5">
      <Field label="Full Name" required error={errors.name}>
        <input
          className={`field-input ${errors.name ? 'error' : ''}`}
          placeholder="John Smith"
          value={data.name}
          onChange={e => onChange('name', e.target.value)}
        />
      </Field>
      <Field label="Company" error={errors.company}>
        <input
          className="field-input"
          placeholder="Smith Heavy Haul (optional)"
          value={data.company}
          onChange={e => onChange('company', e.target.value)}
        />
      </Field>
      <Field label="Email" required error={errors.email}>
        <input
          type="email"
          className={`field-input ${errors.email ? 'error' : ''}`}
          placeholder="you@example.com"
          value={data.email}
          onChange={e => onChange('email', e.target.value)}
        />
      </Field>
      <Field label="Phone" error={errors.phone}>
        <input
          type="tel"
          className={`field-input ${errors.phone ? 'error' : ''}`}
          placeholder="(xxx) xxx-xxxx"
          value={data.phone}
          onChange={e => onChange('phone', e.target.value)}
        />
      </Field>
    </div>
  </div>
);

const MoveDetailsSection = ({
  data, errors, onChange, onToggleState,
}: {
  data: FormData;
  errors: Errors;
  onChange: (field: keyof FormData, val: string) => void;
  onToggleState: (state: string) => void;
}) => (
  <div>
    <SectionHeader label="02" title="MOVE DETAILS" />
    <div className="space-y-5">
      <div className="grid md:grid-cols-2 gap-5">
        <Field label="Origin" required error={errors.origin}>
          <input
            className={`field-input ${errors.origin ? 'error' : ''}`}
            placeholder="City, State"
            value={data.origin}
            onChange={e => onChange('origin', e.target.value)}
          />
        </Field>
        <Field label="Destination" required error={errors.destination}>
          <input
            className={`field-input ${errors.destination ? 'error' : ''}`}
            placeholder="City, State"
            value={data.destination}
            onChange={e => onChange('destination', e.target.value)}
          />
        </Field>
      </div>

      <Field label="Requested Date / Time Window" error={errors.dateWindow}>
        <input
          className="field-input"
          placeholder="e.g. July 15–17, morning preferred"
          value={data.dateWindow}
          onChange={e => onChange('dateWindow', e.target.value)}
        />
      </Field>

      <Field label="Load Description" required error={errors.loadDescription}>
        <textarea
          className={`field-input ${errors.loadDescription ? 'error' : ''}`}
          rows={3}
          placeholder="Describe the load (type, trailer config, special requirements...)"
          value={data.loadDescription}
          onChange={e => onChange('loadDescription', e.target.value)}
          style={{ resize: 'vertical' }}
        />
      </Field>

      {/* Dimensions */}
      <div>
        <label className="field-label">Dimensions (optional)</label>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {(['height', 'width', 'length', 'weight'] as const).map(dim => (
            <div key={dim} className="relative">
              <input
                className="field-input"
                type="number"
                placeholder={dim.charAt(0).toUpperCase() + dim.slice(1)}
                value={data[dim]}
                onChange={e => onChange(dim, e.target.value)}
              />
              <span
                className="absolute right-3 top-1/2 -translate-y-1/2 mono-font text-xs pointer-events-none"
                style={{ color: 'var(--color-muted)' }}
              >
                {dim === 'weight' ? 'lbs' : 'ft'}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* States */}
      <div>
        <label className="field-label">States Involved</label>
        <div className="flex flex-wrap gap-2 mt-1">
          {STATES.map(s => (
            <button
              key={s}
              type="button"
              onClick={() => onToggleState(s)}
              className="mono-font text-xs px-3 py-1.5 rounded transition-all"
              style={{
                border: data.statesInvolved.includes(s)
                  ? '1px solid var(--color-accent)'
                  : '1px solid var(--color-border)',
                background: data.statesInvolved.includes(s)
                  ? 'rgba(244,167,21,0.12)'
                  : 'var(--color-surface)',
                color: data.statesInvolved.includes(s)
                  ? 'var(--color-accent)'
                  : 'var(--color-muted)',
              }}
            >
              {s}
            </button>
          ))}
        </div>
      </div>
    </div>
  </div>
);

const ServiceTypeSection = ({
  data, errors, onToggleService,
}: {
  data: FormData; errors: Errors; onToggleService: (s: string) => void;
}) => (
  <div>
    <SectionHeader label="03" title="SERVICE TYPE" />
    {errors.serviceTypes && <p className="field-error mb-3">{errors.serviceTypes}</p>}
    <div className="grid sm:grid-cols-2 gap-3">
      {SERVICE_TYPES.map(svc => {
        const active = data.serviceTypes.includes(svc);
        return (
          <button
            key={svc}
            type="button"
            onClick={() => onToggleService(svc)}
            className="flex items-center gap-3 p-4 rounded text-left transition-all"
            style={{
              border: active ? '1px solid var(--color-accent)' : '1px solid var(--color-border)',
              background: active ? 'rgba(244,167,21,0.06)' : 'var(--color-surface)',
            }}
          >
            <div
              className="w-4 h-4 rounded flex items-center justify-center flex-shrink-0"
              style={{
                border: active ? '1px solid var(--color-accent)' : '1px solid var(--color-border)',
                background: active ? 'var(--color-accent)' : 'transparent',
              }}
            >
              {active && <span style={{ color: '#0a0c0f', fontSize: '10px', fontWeight: 700 }}>✓</span>}
            </div>
            <span className="text-sm" style={{ color: active ? 'var(--color-text)' : 'var(--color-muted)' }}>
              {svc}
            </span>
          </button>
        );
      })}
    </div>
  </div>
);

const SectionHeader = ({ label, title }: { label: string; title: string }) => (
  <div className="flex items-center gap-4 mb-6">
    <span className="mono-font text-xs" style={{ color: 'var(--color-accent)' }}>{label}</span>
    <span className="display-font text-2xl" style={{ color: 'var(--color-text)' }}>{title}</span>
    <div className="flex-1 h-px" style={{ background: 'var(--color-border)' }} />
  </div>
);

// ── Main Page ─────────────────────────────────────────────────
const RequestPage: React.FC = () => {
  const [form, setForm] = useState<FormData>(INITIAL_FORM);
  const [errors, setErrors] = useState<Errors>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleChange = (field: keyof FormData, val: string) => {
    setForm(f => ({ ...f, [field]: val }));
    if (errors[field]) setErrors(e => { const n = { ...e }; delete n[field]; return n; });
  };

  const toggleState = (s: string) => {
    setForm(f => ({
      ...f,
      statesInvolved: f.statesInvolved.includes(s)
        ? f.statesInvolved.filter(x => x !== s)
        : [...f.statesInvolved, s],
    }));
  };

  const toggleService = (s: string) => {
    setForm(f => ({
      ...f,
      serviceTypes: f.serviceTypes.includes(s)
        ? f.serviceTypes.filter(x => x !== s)
        : [...f.serviceTypes, s],
    }));
    if (errors.serviceTypes) setErrors(e => { const n = { ...e }; delete n.serviceTypes; return n; });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs = validate(form);
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      const first = document.querySelector('.field-input.error');
      first?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }

    setSubmitting(true);

    // TODO: Replace with real API call
    // await fetch('/api/requests', { method: 'POST', body: JSON.stringify(form) });
    await new Promise(res => setTimeout(res, 900));
    console.log('[REQUEST SUBMITTED]', form);

    setSubmitting(false);
    setSubmitted(true);
  };

  if (submitted) {
    return (
      <div className="min-h-screen flex flex-col" style={{ background: 'var(--color-bg)' }}>
        <PublicNav />
        <div className="flex-1 flex items-center justify-center px-6 pt-20">
          <div
            className="max-w-md w-full p-10 rounded-lg text-center"
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
            }}
          >
            <CheckCircle size={48} className="mx-auto mb-5" style={{ color: 'var(--color-success)' }} />
            <h2 className="display-font text-4xl mb-3" style={{ color: 'var(--color-text)' }}>
              REQUEST RECEIVED
            </h2>
            <p className="text-sm mb-8" style={{ color: 'var(--color-muted)' }}>
              We'll review your move details and follow up within one business day.
            </p>
            <Link to="/">
              <button className="btn-primary w-full">BACK TO HOME</button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ background: 'var(--color-bg)' }}>
      <PublicNav />
      <div className="max-w-3xl mx-auto px-6 pt-28 pb-20">
        {/* Page header */}
        <Link
          to="/"
          className="flex items-center gap-2 text-sm mb-8 transition-colors hover:text-white"
          style={{ color: 'var(--color-muted)' }}
        >
          <ArrowLeft size={14} />
          Back to home
        </Link>

        <div className="mb-10">
          <div className="flex items-center gap-3 mb-3">
            <span className="accent-line" />
            <span className="mono-font text-xs tracking-widest" style={{ color: 'var(--color-accent)' }}>
              GIGATT TRANSPORT LLC
            </span>
          </div>
          <h1 className="display-font text-5xl md:text-6xl" style={{ color: 'var(--color-text)' }}>
            REQUEST A<br />ROUTE / JOB
          </h1>
          <p className="mt-4 text-sm" style={{ color: 'var(--color-muted)' }}>
            Fill out the form below and we'll review your request and follow up within one business day.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-12">
          <ContactSection data={form} errors={errors} onChange={handleChange} />
          <MoveDetailsSection
            data={form} errors={errors}
            onChange={handleChange} onToggleState={toggleState}
          />
          <ServiceTypeSection data={form} errors={errors} onToggleService={toggleService} />

          {/* Notes */}
          <div>
            <SectionHeader label="04" title="ADDITIONAL NOTES" />
            <textarea
              className="field-input"
              rows={4}
              placeholder="Anything else we should know about this move..."
              value={form.additionalNotes}
              onChange={e => handleChange('additionalNotes', e.target.value)}
              style={{ resize: 'vertical' }}
            />
          </div>

          {/* Submit */}
          <div className="pt-2">
            <button
              type="submit"
              className="btn-primary w-full sm:w-auto text-base"
              disabled={submitting}
            >
              {submitting ? 'SUBMITTING...' : 'SUBMIT REQUEST'}
            </button>
            <p className="text-xs mt-3" style={{ color: 'var(--color-muted)' }}>
              * Required fields. We don't share your info with third parties.
            </p>
          </div>
        </form>
      </div>
    </div>
  );
};

export default RequestPage;
