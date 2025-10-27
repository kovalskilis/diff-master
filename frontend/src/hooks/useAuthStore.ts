import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { authAPI } from '@/services/api';
import type { User } from '@/types';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

  login: async (email: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      // Client-side guard: bcrypt accepts up to 72 bytes
      const pwdBytes = new TextEncoder().encode(password).length;
      if (password.length < 8) {
        throw { response: { data: { message: 'Пароль должен содержать минимум 8 символов' } } };
      }
      if (pwdBytes > 72) {
        throw { response: { data: { message: 'Пароль не может быть длиннее 72 байт' } } };
      }
      const data = await authAPI.login(email, password);
      const token = data.access_token;
      localStorage.setItem('token', token);
      
      const user = await authAPI.getMe();
      set({ user, token, isAuthenticated: true, isLoading: false });
    } catch (error: any) {
      const data = error?.response?.data;
      const msg = data?.message || data?.detail || (Array.isArray(data?.errors) ? data.errors.map((e: any) => (e.field ? `${e.field}: ${e.message}` : e.message)).join(', ') : null) || 'Ошибка входа';
      set({ error: msg, isLoading: false });
      throw error;
    }
  },

  register: async (email: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      // Client-side guard: bcrypt accepts up to 72 bytes
      const pwdBytes = new TextEncoder().encode(password).length;
      if (password.length < 8) {
        throw { response: { data: { message: 'Пароль должен содержать минимум 8 символов' } } };
      }
      if (pwdBytes > 72) {
        throw { response: { data: { message: 'Пароль не может быть длиннее 72 байт' } } };
      }
      await authAPI.register(email, password);
      set({ isLoading: false });
    } catch (error: any) {
      const data = error?.response?.data;
      const msg = data?.message || data?.detail || (Array.isArray(data?.errors) ? data.errors.map((e: any) => (e.field ? `${e.field}: ${e.message}` : e.message)).join(', ') : null) || 'Ошибка регистрации';
      set({ error: msg, isLoading: false });
      throw error;
    }
  },

  logout: async () => {
    try {
      await authAPI.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      localStorage.removeItem('token');
      set({ user: null, token: null, isAuthenticated: false });
    }
  },

  checkAuth: async () => {
    const token = localStorage.getItem('token');
    if (!token) {
      set({ isAuthenticated: false, isLoading: false });
      return;
    }

    set({ isLoading: true });
    try {
      const user = await authAPI.getMe();
      set({ user, token, isAuthenticated: true, isLoading: false });
    } catch (error: any) {
      // If 401, clear everything and redirect to login
      if (error.response?.status === 401) {
        localStorage.removeItem('token');
        localStorage.removeItem('auth-storage');
        set({ user: null, token: null, isAuthenticated: false, isLoading: false });
        window.location.href = '/login';
      } else {
        // For other errors, just clear token but don't redirect
        localStorage.removeItem('token');
        set({ user: null, token: null, isAuthenticated: false, isLoading: false });
      }
    }
  },

  clearError: () => set({ error: null }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ 
        token: state.token, 
        isAuthenticated: state.isAuthenticated,
        user: state.user 
      }),
    }
  )
);

