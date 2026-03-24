import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { api } from '../services/api';
import type { LoginResponse, Perfil } from '../types';

const TOKEN_KEY = 'roteiro_token';
const PERFIL_KEY = 'roteiro_perfil';

type AuthState = {
  token: string | null;
  perfil: Perfil | null;
  login: (email: string, senha: string) => Promise<LoginResponse>;
  logout: () => void;
  isAuthenticated: boolean;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [perfil, setPerfil] = useState<Perfil | null>(() => {
    const p = localStorage.getItem(PERFIL_KEY);
    return p === 'vendedor' || p === 'proprietaria' ? p : null;
  });

  const login = useCallback(async (email: string, senha: string) => {
    const r = await api<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, senha }),
    });
    localStorage.setItem(TOKEN_KEY, r.token);
    localStorage.setItem(PERFIL_KEY, r.perfil);
    setToken(r.token);
    setPerfil(r.perfil);
    return r;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(PERFIL_KEY);
    setToken(null);
    setPerfil(null);
  }, []);

  const value = useMemo(
    () => ({
      token,
      perfil,
      login,
      logout,
      isAuthenticated: Boolean(token),
    }),
    [token, perfil, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
