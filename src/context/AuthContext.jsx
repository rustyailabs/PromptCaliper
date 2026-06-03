import React, { createContext, useState, useEffect, useCallback } from 'react';
import { authService } from '../services/authService';

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const initialize = useCallback(async () => {
    try {
      const me = await authService.getMe();
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    initialize();

    // Listen for forced logout (from Axios interceptor)
    const handler = () => setUser(null);
    window.addEventListener('ft:logout', handler);
    return () => window.removeEventListener('ft:logout', handler);
  }, [initialize]);

  const login = useCallback(async (username, password) => {
    await authService.login(username, password);
    try {
      const me = await authService.getMe();
      setUser(me || { username });
    } catch {
      // Login already succeeded and tokens are stored; fall back to a minimal user object.
      setUser({ username });
    }
  }, []);

  const logout = useCallback(async () => {
    await authService.logout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: !!user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
