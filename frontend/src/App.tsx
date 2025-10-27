import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from '@/hooks/useAuthStore';
import { LoadingOverlay } from '@/components/ui/LoadingSpinner';
import { LoginPage } from '@/pages/LoginPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { DocumentPage } from '@/pages/DocumentPage';
import { ReviewPage } from '@/pages/ReviewPage';
import { DiffPage } from '@/pages/DiffPage';
import { EditsPage } from '@/pages/EditsPage';

// Protected Route Component
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, isLoading } = useAuthStore();

  if (isLoading) {
    return <LoadingOverlay message="Проверка аутентификации..." />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

function App() {
  const { checkAuth, isLoading, isAuthenticated, token } = useAuthStore();

  useEffect(() => {
    // Check auth on app load if we have a token
    if (token && !isAuthenticated) {
      checkAuth();
    }
  }, []); // Only run once on mount

  // If we have a token but are not authenticated, we're in a loading state
  if (token && !isAuthenticated && !isLoading) {
    return <LoadingOverlay message="Проверка аутентификации..." />;
  }

  if (isLoading) {
    return <LoadingOverlay message="Загрузка приложения..." />;
  }

  return (
    <BrowserRouter>
      <Routes>
        {/* Public Routes */}
        <Route path="/login" element={<LoginPage />} />
        
        {/* Protected Routes */}
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/document/:id"
          element={
            <ProtectedRoute>
              <DocumentPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/review/:workspaceFileId"
          element={
            <ProtectedRoute>
              <ReviewPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/diff/:workspaceFileId"
          element={
            <ProtectedRoute>
              <DiffPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/edits"
          element={
            <ProtectedRoute>
              <EditsPage />
            </ProtectedRoute>
          }
        />
        
        {/* Default Redirect */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;

