import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import AdminLayout from '../../components/admin/AdminLayout';
import StatusBadge from '../../components/StatusBadge';
import { useApp } from '../../context/AppContext';
import { RequestStatus } from '../../types';
import { ArrowLeft, Save, Map, CheckCircle } from 'lucide-react';

const STATUS_OPTIONS: RequestStatus[] = ['new', 'review', 'booked', 'completed', 'rejected'];
const STATUS_LABELS: Record<RequestStatus, string> = {
  new: 'New',
  review: 'In Review',
  booked: 'Booked',
  completed: 'Completed',
  rejected: 'Rejected',
};

const DetailRow = ({ label, value }: { label: string; value?: string }) => (
  <div>
    <div className="text-xs font-semibold tracking-wider mb-1 uppercase" style={{ color: '#9ca3af' }}>
      {label}
    </div>
    <div className="text-sm" style={{ color: value ? '#1a1d23' : '#d1d5db' }}>
      {value || '—'}
    </div>
  </div>
);

const AdminRequestDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { requests, updateRequest } = useApp();
  const navigate = useNavigate();

  const request = requests.find(r => r.id === id);
  const [status, setStatus] = useState<RequestStatus>(request?.status || 'new');
  const [notes, setNotes] = useState(request?.internalNotes || '');
  const [saved, setSaved] = useState(false);

  if (!request) {
    return (
      <AdminLayout>
        <div className="p-8 text-center" style={{ color: '#6b7280' }}>
          Request not found.
          <button onClick={() => navigate('/admin/requests')} className="block mx-auto mt-4 text-sm text-blue-600">
            Back to list
          </button>
        </div>
      </AdminLayout>
    );
  }

  const handleSave = () => {
    // TODO: Replace with real API PATCH call
    updateRequest(request.id, { status, internalNotes: notes });
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  const handleOpenGeomapper = () => {
    // TODO: Wire to Geomapper app with route data
    console.log('[GEOMAPPER] Opening with:', { origin: request.origin, destination: request.destination, id: request.id });
    alert('TODO: Open in Geomapper — see console for route data');
  };

  return (
    <AdminLayout>
      <div className="p-8 max-w-5xl">
        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <button
            onClick={() => navigate('/admin/requests')}
            className="flex items-center gap-1.5 text-sm transition-colors hover:text-gray-700"
            style={{ color: '#9ca3af' }}
          >
            <ArrowLeft size={14} />
            Back
          </button>
          <span style={{ color: '#e5e7eb' }}>|</span>
          <span className="font-mono text-xs" style={{ color: '#9ca3af' }}>{request.id}</span>
          <StatusBadge status={request.status} />
        </div>

        <h1 className="text-xl font-bold mb-1" style={{ color: '#1a1d23' }}>
          {request.name}
          {request.company && (
            <span className="text-base font-normal ml-2" style={{ color: '#9ca3af' }}>
              — {request.company}
            </span>
          )}
        </h1>
        <p className="text-sm mb-8" style={{ color: '#6b7280' }}>
          {request.origin} → {request.destination}
        </p>

        <div className="grid md:grid-cols-3 gap-6">
          {/* Left: Request details */}
          <div className="md:col-span-2 space-y-5">
            {/* Contact */}
            <div className="admin-card p-6">
              <h3 className="text-xs font-bold tracking-widest uppercase mb-4" style={{ color: '#9ca3af' }}>
                Contact
              </h3>
              <div className="grid grid-cols-2 gap-4">
                <DetailRow label="Name" value={request.name} />
                <DetailRow label="Company" value={request.company} />
                <DetailRow label="Email" value={request.email} />
                <DetailRow label="Phone" value={request.phone} />
              </div>
            </div>

            {/* Move Details */}
            <div className="admin-card p-6">
              <h3 className="text-xs font-bold tracking-widest uppercase mb-4" style={{ color: '#9ca3af' }}>
                Move Details
              </h3>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <DetailRow label="Origin" value={request.origin} />
                <DetailRow label="Destination" value={request.destination} />
                <DetailRow label="Date Window" value={request.dateWindow} />
                <DetailRow label="States Involved" value={request.statesInvolved.join(', ') || undefined} />
              </div>
              <DetailRow label="Load Description" value={request.loadDescription} />

              {(request.height || request.width || request.length || request.weight) && (
                <div className="grid grid-cols-4 gap-3 mt-4 pt-4" style={{ borderTop: '1px solid #f3f4f6' }}>
                  <DetailRow label="Height (ft)" value={request.height} />
                  <DetailRow label="Width (ft)" value={request.width} />
                  <DetailRow label="Length (ft)" value={request.length} />
                  <DetailRow label="Weight (lbs)" value={request.weight} />
                </div>
              )}
            </div>

            {/* Service Types */}
            <div className="admin-card p-6">
              <h3 className="text-xs font-bold tracking-widest uppercase mb-4" style={{ color: '#9ca3af' }}>
                Service Type
              </h3>
              <div className="flex flex-wrap gap-2">
                {request.serviceTypes.map(s => (
                  <span
                    key={s}
                    className="text-xs px-3 py-1.5 rounded"
                    style={{ background: '#eff6ff', color: '#1d4ed8', border: '1px solid #dbeafe' }}
                  >
                    {s}
                  </span>
                ))}
              </div>
              {request.additionalNotes && (
                <div className="mt-4 pt-4" style={{ borderTop: '1px solid #f3f4f6' }}>
                  <DetailRow label="Additional Notes" value={request.additionalNotes} />
                </div>
              )}
            </div>
          </div>

          {/* Right: Admin controls */}
          <div className="space-y-5">
            {/* Status */}
            <div className="admin-card p-5">
              <h3 className="text-xs font-bold tracking-widest uppercase mb-3" style={{ color: '#9ca3af' }}>
                Status
              </h3>
              <select
                className="admin-input mb-1"
                value={status}
                onChange={e => setStatus(e.target.value as RequestStatus)}
              >
                {STATUS_OPTIONS.map(s => (
                  <option key={s} value={s}>{STATUS_LABELS[s]}</option>
                ))}
              </select>
            </div>

            {/* Internal Notes */}
            <div className="admin-card p-5">
              <h3 className="text-xs font-bold tracking-widest uppercase mb-3" style={{ color: '#9ca3af' }}>
                Internal Notes
              </h3>
              <textarea
                className="admin-input"
                rows={5}
                placeholder="Internal notes (not visible to customer)"
                value={notes}
                onChange={e => setNotes(e.target.value)}
                style={{ resize: 'vertical' }}
              />
            </div>

            {/* Actions */}
            <div className="space-y-2">
              <button
                onClick={handleSave}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded text-sm font-medium text-white transition-all"
                style={{ background: saved ? '#059669' : '#1a3a5c' }}
              >
                {saved ? (
                  <>
                    <CheckCircle size={14} />
                    Saved
                  </>
                ) : (
                  <>
                    <Save size={14} />
                    Save Changes
                  </>
                )}
              </button>

              {/* TODO: Wire to Geomapper app */}
              <button
                onClick={handleOpenGeomapper}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded text-sm font-medium transition-all border"
                style={{
                  background: 'transparent',
                  color: '#f4a715',
                  borderColor: '#f4a715',
                }}
              >
                <Map size={14} />
                Open in Geomapper
              </button>
              <p className="text-xs text-center" style={{ color: '#9ca3af' }}>
                {/* TODO: Replace with real Geomapper navigation */}
                Geomapper integration pending
              </p>
            </div>

            {/* Meta */}
            <div className="admin-card p-5">
              <h3 className="text-xs font-bold tracking-widest uppercase mb-3" style={{ color: '#9ca3af' }}>
                Meta
              </h3>
              <div className="space-y-2">
                <DetailRow
                  label="Submitted"
                  value={new Date(request.createdAt).toLocaleString('en-US', {
                    dateStyle: 'medium', timeStyle: 'short',
                  })}
                />
                <DetailRow label="Request ID" value={request.id} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
};

export default AdminRequestDetail;
