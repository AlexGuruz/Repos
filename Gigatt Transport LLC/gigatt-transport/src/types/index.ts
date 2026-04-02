export type RequestStatus = 'new' | 'review' | 'booked' | 'completed' | 'rejected';

export interface MoveRequest {
  id: string;
  createdAt: string;
  // Contact
  name: string;
  company?: string;
  email: string;
  phone?: string;
  // Move
  origin: string;
  destination: string;
  dateWindow: string;
  loadDescription: string;
  height?: string;
  width?: string;
  length?: string;
  weight?: string;
  statesInvolved: string[];
  // Service
  serviceTypes: string[];
  additionalNotes?: string;
  // Admin
  status: RequestStatus;
  internalNotes?: string;
}

export interface AuthState {
  isAuthenticated: boolean;
  username?: string;
}
