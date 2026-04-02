import React, { createContext, useContext, useState, ReactNode } from 'react';
import { MoveRequest, AuthState } from '../types';
import { MOCK_REQUESTS } from '../data/mockData';

interface AppContextType {
  auth: AuthState;
  login: (username: string, password: string) => boolean;
  logout: () => void;
  requests: MoveRequest[];
  updateRequest: (id: string, updates: Partial<MoveRequest>) => void;
}

const AppContext = createContext<AppContextType | null>(null);

export const AppProvider = ({ children }: { children: ReactNode }) => {
  const [auth, setAuth] = useState<AuthState>({ isAuthenticated: false });
  const [requests, setRequests] = useState<MoveRequest[]>(MOCK_REQUESTS);

  // TODO: Replace with real API auth call
  const login = (username: string, password: string): boolean => {
    if (username === 'admin' && password === 'gigatt') {
      setAuth({ isAuthenticated: true, username });
      return true;
    }
    return false;
  };

  const logout = () => setAuth({ isAuthenticated: false });

  // TODO: Replace with real API PATCH call
  const updateRequest = (id: string, updates: Partial<MoveRequest>) => {
    setRequests(prev =>
      prev.map(r => (r.id === id ? { ...r, ...updates } : r))
    );
  };

  return (
    <AppContext.Provider value={{ auth, login, logout, requests, updateRequest }}>
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
};
