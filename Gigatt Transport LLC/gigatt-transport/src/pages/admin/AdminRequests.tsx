import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AdminLayout from '../../components/admin/AdminLayout';
import StatusBadge from '../../components/StatusBadge';
import { useApp } from '../../context/AppContext';
import { RequestStatus } from '../../types';
import { ChevronRight, Filter } from 'lucide-react';

const ALL_STATUSES: (RequestStatus | 'all')[] = ['all', 'new', 'review', 'booked', 'completed', 'rejected'];
const STATUS_LABELS: Record<RequestStatus | 'all', string> = {
  all: 'All',
  new: 'New',
  review: 'In Review',
  booked: 'Booked',
  completed: 'Completed',
  rejected: 'Rejected',
};

const AdminRequests: React.FC = () => {
  const { requests } = useApp();
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<RequestStatus | 'all'>('all');

  const filtered = statusFilter === 'all'
    ? requests
    : requests.filter(r => r.status === statusFilter);

  const formatDate = (iso: string) => {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    });
  };

  return (
    <AdminLayout>
      <div className="p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold" style={{ color: '#1a1d23' }}>
              Route Requests
            </h1>
            <p className="text-sm mt-0.5" style={{ color: '#6b7280' }}>
              {requests.length} total requests
            </p>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2 mb-5">
          <Filter size={14} style={{ color: '#6b7280' }} />
          <div className="flex gap-1.5 flex-wrap">
            {ALL_STATUSES.map(s => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className="text-xs px-3 py-1.5 rounded-full border transition-all"
                style={{
                  background: statusFilter === s ? '#1a3a5c' : '#fff',
                  color: statusFilter === s ? '#fff' : '#6b7280',
                  borderColor: statusFilter === s ? '#1a3a5c' : '#e2e5ea',
                  fontWeight: statusFilter === s ? 500 : 400,
                }}
              >
                {STATUS_LABELS[s]}
              </button>
            ))}
          </div>
        </div>

        {/* Table */}
        <div className="admin-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--admin-border)', background: '#f9fafb' }}>
                  {['Date', 'Contact', 'Route', 'States', 'Service', 'Status', ''].map(col => (
                    <th
                      key={col}
                      className="text-left px-5 py-3 text-xs font-semibold tracking-wider"
                      style={{ color: '#6b7280' }}
                    >
                      {col.toUpperCase()}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-5 py-10 text-center text-sm" style={{ color: '#9ca3af' }}>
                      No requests found
                    </td>
                  </tr>
                )}
                {filtered.map((req, i) => (
                  <tr
                    key={req.id}
                    onClick={() => navigate(`/admin/requests/${req.id}`)}
                    className="cursor-pointer transition-colors hover:bg-blue-50"
                    style={{
                      borderBottom: i < filtered.length - 1 ? '1px solid #f3f4f6' : 'none',
                    }}
                  >
                    <td className="px-5 py-4 text-xs font-mono" style={{ color: '#6b7280', whiteSpace: 'nowrap' }}>
                      {formatDate(req.createdAt)}
                    </td>
                    <td className="px-5 py-4">
                      <div className="font-medium text-sm" style={{ color: '#1a1d23' }}>{req.name}</div>
                      {req.company && (
                        <div className="text-xs" style={{ color: '#9ca3af' }}>{req.company}</div>
                      )}
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-1.5 text-xs" style={{ color: '#374151' }}>
                        <span>{req.origin}</span>
                        <ChevronRight size={11} style={{ color: '#9ca3af' }} />
                        <span>{req.destination}</span>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex gap-1 flex-wrap">
                        {req.statesInvolved.slice(0, 3).map(s => (
                          <span
                            key={s}
                            className="text-xs px-1.5 py-0.5 rounded font-mono"
                            style={{ background: '#f3f4f6', color: '#6b7280' }}
                          >
                            {s}
                          </span>
                        ))}
                        {req.statesInvolved.length > 3 && (
                          <span className="text-xs" style={{ color: '#9ca3af' }}>
                            +{req.statesInvolved.length - 3}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <div className="text-xs max-w-32 truncate" style={{ color: '#6b7280' }}>
                        {req.serviceTypes.join(', ')}
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <StatusBadge status={req.status} />
                    </td>
                    <td className="px-5 py-4">
                      <ChevronRight size={16} style={{ color: '#d1d5db' }} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
};

export default AdminRequests;
