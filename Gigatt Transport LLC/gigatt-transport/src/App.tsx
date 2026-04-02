import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import ProtectedRoute from './components/ProtectedRoute';

import LandingPage from './pages/LandingPage';
import RequestPage from './pages/RequestPage';
import AdminLogin from './pages/admin/AdminLogin';
import AdminRequests from './pages/admin/AdminRequests';
import AdminRequestDetail from './pages/admin/AdminRequestDetail';

const App: React.FC = () => {
  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/request" element={<RequestPage />} />
          <Route path="/admin/login" element={<AdminLogin />} />
          <Route
            path="/admin/requests"
            element={
              <ProtectedRoute>
                <AdminRequests />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/requests/:id"
            element={
              <ProtectedRoute>
                <AdminRequestDetail />
              </ProtectedRoute>
            }
          />
          <Route path="/admin" element={<Navigate to="/admin/login" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AppProvider>
  );
};

export default App;
