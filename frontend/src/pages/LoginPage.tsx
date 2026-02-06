import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

// Страница логина отключена - автоматически перенаправляем на dashboard
export const LoginPage = () => {
  const navigate = useNavigate();

  useEffect(() => {
    // Перенаправляем на dashboard
    navigate('/dashboard', { replace: true });
  }, [navigate]);

  return null;
};
