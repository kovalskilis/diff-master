// аглушка - аутентификация отключена
export const useAuthStore = () => {
  return {
    isAuthenticated: true,
    user: { id: '1', email: 'test@example.com', name: 'Test User' },
    token: 'mock-token',
    isLoading: false,
    login: async () => {},
    logout: () => {},
    setLoading: () => {}
  };
};
