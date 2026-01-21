/**
 * Auth store stub - authentication is disabled
 * This file provides a minimal interface for compatibility with existing code
 */
import { create } from 'zustand';
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

// Dummy user for compatibility
const dummyUser: User = {
  id: '00000000-0000-0000-0000-000000000001',
  email: 'dummy@example.com',
  is_active: true,
  is_superuser: false,
  is_verified: true,
};

// Stub implementation using zustand - all methods are no-ops
export const useAuthStore = create<AuthState>()((set) => ({
  user: dummyUser,
  token: null,
  isAuthenticated: true, // Always authenticated when auth is disabled
  isLoading: false,
  error: null,
  
  login: async () => {
    // No-op - authentication disabled
  },
  
  register: async () => {
    // No-op - authentication disabled
  },
  
  logout: async () => {
    // No-op - authentication disabled
  },
  
  checkAuth: async () => {
    // No-op - always authenticated when auth is disabled
    set({ isAuthenticated: true, user: dummyUser });
  },
  
  clearError: () => {
    set({ error: null });
  },
}));
