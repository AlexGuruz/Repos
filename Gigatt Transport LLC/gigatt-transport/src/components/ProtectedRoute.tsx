import React from 'react';
import { Navigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';

interface Props {
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<Props> = ({ children }) => {
  const { auth } = useApp();
  if (!auth.isAuthenticated) {
    return <Navigate to="/admin/login" replace />;
  }
  return <>{children}</>;
};

export default ProtectedRoute;
