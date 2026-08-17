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
import { clearFinanceLocalCaches } from "@/lib/finance-local-cache";
import {
  loginResponseSchema,
  magicCodeRequestResponseSchema,
  magicCodeStatusSchema,
  sessionResponseSchema,
  type UserInfo,
} from "@/lib/schemas";

type MagicCodeRequestResult = {
  message: string;
  expiresInSeconds: number;
  devCode?: string | null;
  devLink?: string | null;
};

type AuthContextValue = {
  user: UserInfo | null;
  loading: boolean;
  magicCodeEnabled: boolean;
  magicCodeDevDelivery: boolean;
  login: (username: string, password: string) => Promise<void>;
  requestMagicCode: (email: string) => Promise<MagicCodeRequestResult>;
  verifyMagicCode: (email: string, code: string) => Promise<void>;
  consumeMagicLink: (token: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [magicCodeEnabled, setMagicCodeEnabled] = useState(true);
  const [magicCodeDevDelivery, setMagicCodeDevDelivery] = useState(false);

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
    // Never leave the UI on “Loading session…” if a bootstrap request stalls
    // past the per-request abort (e.g. proxy/rewrite oddities on hosted deploys).
    const failSafe = window.setTimeout(() => {
      if (!active) return;
      setUser(null);
      setCsrfToken(null);
      setLoading(false);
    }, 10000);
    (async () => {
      try {
        const [session, magicStatus] = await Promise.all([
          apiClient.get("/auth/me").catch(() => null),
          apiClient.get("/auth/magic-code/status").catch(() => null),
        ]);
        if (!active) return;
        if (session) {
          const data = sessionResponseSchema.parse(session);
          setUser(data.user);
          setCsrfToken(data.csrf_token);
        } else {
          setUser(null);
          setCsrfToken(null);
        }
        if (magicStatus) {
          const status = magicCodeStatusSchema.parse(magicStatus);
          setMagicCodeEnabled(status.enabled);
          setMagicCodeDevDelivery(Boolean(status.dev_delivery));
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
      window.clearTimeout(failSafe);
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const data = loginResponseSchema.parse(
      await apiClient.post("/auth/login", { username, password }),
    );
    setCsrfToken(data.csrf_token);
    setUser(data.user);
  }, []);

  const requestMagicCode = useCallback(async (email: string) => {
    const data = magicCodeRequestResponseSchema.parse(
      await apiClient.post("/auth/magic-code/request", { email }),
    );
    return {
      message: data.message,
      expiresInSeconds: data.expires_in_seconds,
      devCode: data.dev_code,
      devLink: data.dev_link,
    };
  }, []);

  const verifyMagicCode = useCallback(async (email: string, code: string) => {
    const data = loginResponseSchema.parse(
      await apiClient.post("/auth/magic-code/verify", { email, code }),
    );
    setCsrfToken(data.csrf_token);
    setUser(data.user);
  }, []);

  const consumeMagicLink = useCallback(async (token: string) => {
    const data = loginResponseSchema.parse(
      await apiClient.post("/auth/magic-link/consume", { token }),
    );
    setCsrfToken(data.csrf_token);
    setUser(data.user);
  }, []);

  const logout = useCallback(async () => {
    // Clear caches and drop the session before the network round-trip so
    // in-flight finance writers cannot repopulate last-known figures, and so
    // hooks stop starting new fetches while logout is still awaiting.
    clearFinanceLocalCaches();
    setUser(null);
    setCsrfToken(null);
    try {
      await apiClient.post("/auth/logout");
    } catch {
      // Local session already cleared even if the server is unreachable.
    }
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      magicCodeEnabled,
      magicCodeDevDelivery,
      login,
      requestMagicCode,
      verifyMagicCode,
      consumeMagicLink,
      logout,
      refreshUser,
    }),
    [
      user,
      loading,
      magicCodeEnabled,
      magicCodeDevDelivery,
      login,
      requestMagicCode,
      verifyMagicCode,
      consumeMagicLink,
      logout,
      refreshUser,
    ],
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
