import React from 'react';
import { RequestStatus } from '../types';

interface Props {
  status: RequestStatus;
}

const labels: Record<RequestStatus, string> = {
  new: 'New',
  review: 'In Review',
  booked: 'Booked',
  completed: 'Completed',
  rejected: 'Rejected',
};

const StatusBadge: React.FC<Props> = ({ status }) => {
  return (
    <span className={`status-badge status-${status}`}>
      {labels[status]}
    </span>
  );
};

export default StatusBadge;
