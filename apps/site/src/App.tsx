import { Navigate, Route, Routes } from 'react-router-dom';
import { HomePage } from './pages/HomePage';
import { PlansPage } from './pages/PlansPage';
import { NotFoundPage } from './pages/NotFoundPage';

export function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/plans" element={<PlansPage />} />
      <Route path="/404" element={<NotFoundPage />} />
      <Route path="*" element={<Navigate to="/404" replace />} />
    </Routes>
  );
}
