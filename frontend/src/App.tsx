import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useThemeStore } from '@/hooks/useTheme';
import { DashboardPage } from '@/pages/DashboardPage';
import { DocumentPage } from '@/pages/DocumentPage';
import { ReviewPage } from '@/pages/ReviewPage';
import { DiffPage } from '@/pages/DiffPage';
import { EditsPage } from '@/pages/EditsPage';

function App() {
  const { setTheme } = useThemeStore();

  useEffect(() => {
    // Initialize theme
    setTheme(useThemeStore.getState().theme);
  }, []); // Only run once on mount

  return (
    <BrowserRouter>
      <Routes>
        {/* All routes are now public - authentication disabled */}
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/document/:id" element={<DocumentPage />} />
        <Route path="/review/:workspaceFileId" element={<ReviewPage />} />
        <Route path="/diff/:workspaceFileId" element={<DiffPage />} />
        <Route path="/edits" element={<EditsPage />} />
        
        {/* Default Redirect */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;

