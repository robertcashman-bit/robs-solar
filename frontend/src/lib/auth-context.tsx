"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { apiClient, setCsrfToken } from "@/lib/api-client";
import { loginResponseSchema, sessionResponseSchema, type UserInfo } from "@/lib/schemas";

type AuthContextValue = {
  user: UserInfo | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      const data = sessionResponseSchema.parse(await apiClient.get("/auth/me"));
      setUser(data.user);
      setCsrfToken(data.csrf_token);
    } catch {
      setUser(null);
      setCsrfToken(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = sessionResponseSchema.parse(await apiClient.get("/auth/me"));
        if (active) {
          setUser(data.user);
          setCsrfToken(data.csrf_token);
        }
      } catch {
        if (active) {
          setUser(null);
          setCsrfToken(null);
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const data = loginResponseSchema.parse(
      await apiClient.post("/auth/login", { username, password }),
    );
    setCsrfToken(data.csrf_token);
    setUser(data.user);
  }, []);

  const logout = useCallback(async () => {
    await apiClient.post("/auth/logout");
    setUser(null);
    setCsrfToken(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, logout, refreshUser }),
    [user, loading, login, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
