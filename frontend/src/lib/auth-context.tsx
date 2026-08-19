"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { ApiError, apiClient, setCsrfToken } from "@/lib/api-client";
import {
  clearFinanceLocalCaches,
  FINANCE_LAST_SESSION_USER_KEY,
} from "@/lib/finance-local-cache";
import {
  loginResponseSchema,
  magicCodeRequestResponseSchema,
  magicCodeStatusSchema,
  sessionResponseSchema,
  userInfoSchema,
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
  /**
   * True once we have a definitive session answer (authenticated via /auth/me
   * or login, or confirmed 401). Timeouts and network errors do not resolve
   * auth — so a slow cold start cannot look like logout.
   */
  authResolved: boolean;
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

const COOKIE_NOT_STORED_MESSAGE =
  "Sign-in cookie was not stored by the browser. Allow cookies for this site and try again.";

function isUnauthenticatedError(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 401 || error.status === 403);
}

function readCachedSessionUser(): UserInfo | null {
  if (typeof window === "undefined") return null;
  try {
    // Prefer localStorage so a returning logged-in user paints on a cold
    // first tab/entry (sessionStorage is empty after the tab is closed).
    const raw =
      window.localStorage.getItem(FINANCE_LAST_SESSION_USER_KEY) ??
      window.sessionStorage.getItem(FINANCE_LAST_SESSION_USER_KEY);
    if (!raw) return null;
    const parsed = userInfoSchema.parse(JSON.parse(raw));
    // Migrate any leftover sessionStorage entry into localStorage once.
    if (!window.localStorage.getItem(FINANCE_LAST_SESSION_USER_KEY)) {
      window.localStorage.setItem(FINANCE_LAST_SESSION_USER_KEY, raw);
      window.sessionStorage.removeItem(FINANCE_LAST_SESSION_USER_KEY);
    }
    return parsed;
  } catch {
    return null;
  }
}

function writeCachedSessionUser(user: UserInfo | null): void {
  if (typeof window === "undefined") return;
  try {
    if (user == null) {
      window.localStorage.removeItem(FINANCE_LAST_SESSION_USER_KEY);
      window.sessionStorage.removeItem(FINANCE_LAST_SESSION_USER_KEY);
    } else {
      window.localStorage.setItem(FINANCE_LAST_SESSION_USER_KEY, JSON.stringify(user));
      window.sessionStorage.removeItem(FINANCE_LAST_SESSION_USER_KEY);
    }
  } catch {
    // ignore private mode
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(() => readCachedSessionUser());
  // Cached session user → do not block first paint on cold /auth/me.
  const [loading, setLoading] = useState(() => readCachedSessionUser() == null);
  // Cached session user lets pages paint immediately; /auth/me still confirms.
  const [authResolved, setAuthResolved] = useState(false);
  const [magicCodeEnabled, setMagicCodeEnabled] = useState(true);
  const [magicCodeDevDelivery, setMagicCodeDevDelivery] = useState(false);
  /** Bumped on login / logout so a stale bootstrap response cannot wipe or restore the session. */
  const authGenerationRef = useRef(0);

  const applySessionUser = useCallback((next: UserInfo, csrf: string) => {
    authGenerationRef.current += 1;
    setCsrfToken(csrf);
    setUser(next);
    writeCachedSessionUser(next);
    setAuthResolved(true);
    setLoading(false);
  }, []);

  /**
   * Login/verify responses set `robs_solar_session` via Set-Cookie. Confirm the
   * browser actually stored it with an immediate /auth/me before treating the
   * user as signed in — otherwise a full page load on Vercel multi-service
   * looks logged-out and kicks them back to /login.
   */
  const confirmSessionCookie = useCallback(
    async (fallback: { user: UserInfo; csrf_token: string }) => {
      try {
        const session = sessionResponseSchema.parse(await apiClient.get("/auth/me"));
        applySessionUser(session.user, session.csrf_token);
      } catch (error) {
        if (isUnauthenticatedError(error)) {
          setUser(null);
          writeCachedSessionUser(null);
          setCsrfToken(null);
          setAuthResolved(true);
          setLoading(false);
          throw new ApiError(COOKIE_NOT_STORED_MESSAGE, 401);
        }
        // Timeout / network after Set-Cookie: keep the login payload so a warm
        // follow-up can succeed; do not claim the cookie failed.
        applySessionUser(fallback.user, fallback.csrf_token);
      }
    },
    [applySessionUser],
  );

  const refreshUser = useCallback(async () => {
    const generation = authGenerationRef.current;
    try {
      const data = sessionResponseSchema.parse(await apiClient.get("/auth/me"));
      if (generation !== authGenerationRef.current) return;
      setUser(data.user);
      writeCachedSessionUser(data.user);
      setCsrfToken(data.csrf_token);
      setAuthResolved(true);
    } catch (error) {
      if (generation !== authGenerationRef.current) return;
      if (isUnauthenticatedError(error)) {
        setUser(null);
        writeCachedSessionUser(null);
        setCsrfToken(null);
        setAuthResolved(true);
      }
      // Timeout / network: leave any existing user alone; do not mark resolved.
    } finally {
      if (generation === authGenerationRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    let active = true;
    const generationAtStart = authGenerationRef.current;
    // Stop an infinite “Loading session…” spinner, but never treat a slow
    // bootstrap as logout — that was kicking valid sessions to /login.
    const failSafe = window.setTimeout(() => {
      if (!active) return;
      setLoading(false);
    }, 10000);
    (async () => {
      try {
        // Warm the serverless function in parallel with session bootstrap.
        void apiClient.get("/health").catch(() => null);
        const [sessionResult, magicStatus] = await Promise.all([
          apiClient
            .get("/auth/me")
            .then((body) => ({ ok: true as const, body }))
            .catch((error: unknown) => ({ ok: false as const, error })),
          apiClient.get("/auth/magic-code/status").catch(() => null),
        ]);
        if (!active) return;
        if (generationAtStart !== authGenerationRef.current) {
          // Login/logout won the race — ignore this bootstrap payload.
          return;
        }
        if (sessionResult.ok) {
          const data = sessionResponseSchema.parse(sessionResult.body);
          setUser(data.user);
          writeCachedSessionUser(data.user);
          setCsrfToken(data.csrf_token);
          setAuthResolved(true);
        } else if (isUnauthenticatedError(sessionResult.error)) {
          setUser(null);
          writeCachedSessionUser(null);
          setCsrfToken(null);
          setAuthResolved(true);
        }
        // else: timeout / 5xx — leave cached user alone and keep auth unresolved
        // so useRequireAuth will not hard-redirect to /login.
        if (magicStatus) {
          const status = magicCodeStatusSchema.parse(magicStatus);
          setMagicCodeEnabled(status.enabled);
          setMagicCodeDevDelivery(Boolean(status.dev_delivery));
        }
      } catch {
        // parse errors etc. — do not clear a user set by login/verify
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

  const login = useCallback(
    async (username: string, password: string) => {
      const data = loginResponseSchema.parse(
        await apiClient.post("/auth/login", { username, password }),
      );
      await confirmSessionCookie(data);
    },
    [confirmSessionCookie],
  );

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

  const verifyMagicCode = useCallback(
    async (email: string, code: string) => {
      const data = loginResponseSchema.parse(
        await apiClient.post("/auth/magic-code/verify", { email, code }),
      );
      await confirmSessionCookie(data);
    },
    [confirmSessionCookie],
  );

  const consumeMagicLink = useCallback(
    async (token: string) => {
      const data = loginResponseSchema.parse(
        await apiClient.post("/auth/magic-link/consume", { token }),
      );
      await confirmSessionCookie(data);
    },
    [confirmSessionCookie],
  );

  const logout = useCallback(async () => {
    // Clear caches and drop the session before the network round-trip so
    // in-flight finance writers cannot repopulate last-known figures, and so
    // hooks stop starting new fetches while logout is still awaiting.
    authGenerationRef.current += 1;
    clearFinanceLocalCaches();
    setUser(null);
    setCsrfToken(null);
    setAuthResolved(true);
    setLoading(false);
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
      authResolved,
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
      authResolved,
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
