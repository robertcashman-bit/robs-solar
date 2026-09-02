"use client";

import { FormEvent, useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";

import { ErrorBanner, SuccessBanner } from "@/components/shared/Banners";
import { WalletIcon } from "@/components/shared/icons";
import { ShortcutInstallCard } from "@/components/shared/ShortcutInstallCard";
import { ApiError, apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { ROBS_FINANCE_OWNER_EMAIL } from "@/lib/hosted";

const LAST_EMAIL_KEY = "robs-finance-last-login-email";
const AUTO_SEND_KEY = "robs-finance-auto-send";

function subscribeLastEmail(onStoreChange: () => void) {
  window.addEventListener("storage", onStoreChange);
  return () => window.removeEventListener("storage", onStoreChange);
}

function readLastEmail() {
  try {
    return window.localStorage.getItem(LAST_EMAIL_KEY) ?? "";
  } catch {
    return "";
  }
}

function subscribeSearch(onStoreChange: () => void) {
  window.addEventListener("popstate", onStoreChange);
  return () => window.removeEventListener("popstate", onStoreChange);
}

function readMagicToken() {
  return new URLSearchParams(window.location.search).get("token") ?? "";
}

function readSendOnOpen() {
  return new URLSearchParams(window.location.search).get("send") === "1";
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

function rememberEmail(value: string) {
  try {
    window.localStorage.setItem(LAST_EMAIL_KEY, value);
  } catch {
    // Ignore blocked storage.
  }
}

export default function LoginPage() {
  const router = useRouter();
  const {
    login,
    user,
    loading,
    magicCodeEnabled,
    magicCodeDevDelivery,
    requestMagicCode,
    verifyMagicCode,
    consumeMagicLink,
  } = useAuth();
  const storedEmail = useSyncExternalStore(subscribeLastEmail, readLastEmail, () => "");
  const magicToken = useSyncExternalStore(subscribeSearch, readMagicToken, () => "");
  const sendOnOpen = useSyncExternalStore(subscribeSearch, readSendOnOpen, () => false);
  const [emailOverride, setEmailOverride] = useState<string | null>(null);
  const email = emailOverride ?? (storedEmail || ROBS_FINANCE_OWNER_EMAIL);
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [devCode, setDevCode] = useState<string | null>(null);
  const [linkSent, setLinkSent] = useState(false);
  const [codeSectionUserOpen, setCodeSectionUserOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [sendingLink, setSendingLink] = useState(false);
  const consumedToken = useRef<string | null>(null);
  // Old Desktop shortcuts still open /login?send=1 — expand the recovery section.
  const codeSectionOpen = codeSectionUserOpen || sendOnOpen || linkSent;

  // Warm the FastAPI service before the user submits so a Vercel
  // Python cold start does not race the session cookie bootstrap.
  useEffect(() => {
    void apiClient.get("/health").catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!loading && user) {
      router.replace("/");
    }
  }, [loading, user, router]);

  useEffect(() => {
    if (!magicToken || consumedToken.current === magicToken) {
      return;
    }
    consumedToken.current = magicToken;
    let cancelled = false;
    setSubmitting(true);
    setError(null);
    setInfo("Signing you in…");
    void consumeMagicLink(magicToken, rememberMe)
      .then(() => {
        if (!cancelled) {
          router.replace("/");
        }
      })
      .catch((linkError: unknown) => {
        if (!cancelled) {
          setError(
            errorMessage(
              linkError,
              "That sign-in link expired. Request a new code below.",
            ),
          );
          setInfo(null);
          setCodeSectionUserOpen(true);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setSubmitting(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [consumeMagicLink, magicToken, rememberMe, router]);

  const handleSendCode = useCallback(async () => {
    setSendingLink(true);
    setError(null);
    setInfo(null);
    setCodeSectionUserOpen(true);
    try {
      const trimmed = email.trim();
      rememberEmail(trimmed);
      const result = await requestMagicCode(trimmed);
      setLinkSent(true);
      setCode("");
      setInfo(result.message);
      setDevCode(result.devCode ?? null);
    } catch (linkError) {
      setError(errorMessage(linkError, "Could not send a sign-in code"));
    } finally {
      setSendingLink(false);
    }
  }, [email, requestMagicCode]);

  useEffect(() => {
    if (!sendOnOpen || !magicCodeEnabled || magicToken || sendingLink || loading || user) {
      return;
    }
    const trimmed = email.trim();
    if (!trimmed.includes("@")) {
      return;
    }
    try {
      if (window.sessionStorage.getItem(AUTO_SEND_KEY) === trimmed) {
        return;
      }
      window.sessionStorage.setItem(AUTO_SEND_KEY, trimmed);
    } catch {
      // Ignore blocked storage and still send once this mount.
    }
    const timer = window.setTimeout(() => {
      void handleSendCode();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [
    sendOnOpen,
    magicCodeEnabled,
    magicToken,
    email,
    loading,
    user,
    sendingLink,
    handleSendCode,
  ]);

  if (!loading && user) {
    return null;
  }

  const handleLogin = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const trimmed = email.trim();
      rememberEmail(trimmed);
      await login(trimmed, password, rememberMe);
      router.replace("/");
    } catch (loginError) {
      setError(errorMessage(loginError, "Login failed"));
    } finally {
      setSubmitting(false);
    }
  };

  const handleVerifyCode = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await verifyMagicCode(email.trim(), code.trim(), rememberMe);
      router.replace("/");
    } catch (verifyError) {
      setError(errorMessage(verifyError, "That code did not work"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div
        className="w-full max-w-md rounded-2xl border border-[var(--border)] bg-[var(--surface-elevated)] p-8 shadow-xl backdrop-blur-xl"
        style={{ boxShadow: "var(--shadow-lg)" }}
      >
        <div className="flex flex-col items-center text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-400 to-teal-600 text-white shadow-lg">
            <WalletIcon size={28} />
          </div>
          <p className="mt-4 text-xs font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
            Rob&apos;s Finance
          </p>
          <h1 className="mt-1 text-2xl font-bold">Sign in</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Enter your email and password. You stay signed in for 30 days.
          </p>
        </div>

        <form onSubmit={(event) => void handleLogin(event)} className="mt-6">
          <label className="block text-sm font-medium" htmlFor="login-email">
            Email or username
            <input
              id="login-email"
              name="username"
              type="text"
              inputMode="email"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              className="solar-input"
              value={email}
              onChange={(event) => setEmailOverride(event.target.value)}
              autoComplete="username"
              required
              placeholder="you@example.com or admin"
              enterKeyHint="next"
            />
          </label>

          <label className="mt-4 block text-sm font-medium" htmlFor="current-password">
            Password
            <input
              id="current-password"
              name="password"
              type="password"
              className="solar-input"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
              enterKeyHint="done"
            />
          </label>

          <label className="mt-4 flex cursor-pointer items-center gap-2 text-sm" htmlFor="remember-me">
            <input
              id="remember-me"
              name="remember"
              type="checkbox"
              className="h-4 w-4 rounded border-[var(--border)]"
              checked={rememberMe}
              onChange={(event) => setRememberMe(event.target.checked)}
            />
            Stay signed in for 30 days
          </label>

          {error && !codeSectionOpen ? (
            <div className="mt-4">
              <ErrorBanner message={error} />
            </div>
          ) : null}

          <button type="submit" disabled={submitting} className="solar-btn-primary mt-6 w-full">
            {submitting ? "Signing in..." : "Sign in"}
          </button>
        </form>

        {magicCodeEnabled ? (
          <details
            className="mt-6 border-t border-[var(--border)] pt-4"
            open={codeSectionOpen}
            onToggle={(event) => setCodeSectionUserOpen(event.currentTarget.open)}
          >
            <summary className="cursor-pointer text-sm font-medium text-[var(--accent)] hover:underline">
              Email me a code instead
            </summary>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Forgot your password? We will email a 6-digit code you can use once.
            </p>
            <button
              type="button"
              disabled={sendingLink || !email.trim()}
              onClick={() => void handleSendCode()}
              className="solar-btn-secondary mt-3 w-full"
            >
              {sendingLink
                ? "Sending code..."
                : linkSent
                  ? "Email me a new code"
                  : "Email me a sign-in code"}
            </button>

            {info ? (
              <div className="mt-3">
                <SuccessBanner message={info} />
              </div>
            ) : null}
            {devCode && magicCodeDevDelivery ? (
              <p className="mt-2 rounded-lg bg-[var(--surface)] px-3 py-2 text-sm">
                Dev code: <span className="font-mono font-semibold tracking-widest">{devCode}</span>
              </p>
            ) : null}
            {error && codeSectionOpen ? (
              <div className="mt-3">
                <ErrorBanner message={error} />
              </div>
            ) : null}

            {linkSent ? (
              <form onSubmit={(event) => void handleVerifyCode(event)} className="mt-4">
                <label className="block text-sm font-medium" htmlFor="login-code">
                  6-digit sign-in code
                  <input
                    id="login-code"
                    name="one-time-code"
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    className="solar-input"
                    value={code}
                    onChange={(event) => setCode(event.target.value)}
                    placeholder="123456"
                    maxLength={6}
                    pattern="[0-9]*"
                    enterKeyHint="done"
                    required
                  />
                </label>
                <button
                  type="submit"
                  disabled={submitting || code.trim().length < 4}
                  className="solar-btn-secondary mt-4 w-full"
                >
                  {submitting ? "Checking..." : "Sign in with code"}
                </button>
              </form>
            ) : null}
          </details>
        ) : null}

        <ShortcutInstallCard />
      </div>
    </div>
  );
}
