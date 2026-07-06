import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import UploadPage from './pages/UploadPage';
import DocTypePage from './pages/DocTypePage';
import ResultPage from './pages/ResultPage';
import DocumentsPage from './pages/DocumentsPage';
import ReviewPage from './pages/ReviewPage';

function AuthGuard({ children }: { children: React.ReactNode }) {
  const user = localStorage.getItem('docverify_user');
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route element={<AuthGuard><Layout /></AuthGuard>}>
          <Route index element={<DashboardPage />} />
          <Route path="upload" element={<UploadPage />} />
          <Route path="verify/:docType" element={<DocTypePage />} />
          <Route path="result/:docId" element={<ResultPage />} />
          <Route path="documents" element={<DocumentsPage />} />
          <Route path="review" element={<ReviewPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
