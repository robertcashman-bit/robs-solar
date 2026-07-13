"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ErrorBanner } from "@/components/shared/Banners";
import { WalletIcon } from "@/components/shared/icons";
import { useAuth } from "@/lib/auth-context";

// Convenience default for this single-user personal dashboard so Rob can sign
// in with one tap. Kept in sync with ADMIN_PASSWORD in backend/.env.
const QUICK_ADMIN = { username: "admin", password: "Greenacre-Solar-4713" };

export default function LoginPage() {
  const router = useRouter();
  const { login, user, loading } = useAuth();
  const [username, setUsername] = useState(QUICK_ADMIN.username);
  const [password, setPassword] = useState(QUICK_ADMIN.password);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && user) {
      router.replace("/");
    }
  }, [loading, user, router]);

  if (!loading && user) {
    return null;
  }

  const signIn = async (creds: { username: string; password: string }) => {
    setSubmitting(true);
    setError(null);
    try {
      await login(creds.username, creds.password);
      router.replace("/");
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    await signIn({ username, password });
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form
        onSubmit={(event) => void handleSubmit(event)}
        className="w-full max-w-md rounded-2xl border border-[var(--border)] bg-[var(--surface-elevated)] p-8 shadow-xl backdrop-blur-xl"
        style={{ boxShadow: "var(--shadow-lg)" }}
      >
        <div className="flex flex-col items-center text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-400 to-teal-600 text-white shadow-lg">
            <WalletIcon size={28} />
          </div>
          <p className="mt-4 text-xs font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
            Rob&apos;s Finance
          </p>
          <h1 className="mt-1 text-2xl font-bold">Sign in</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Personal and business finance dashboard.
          </p>
        </div>

        <button
          type="button"
          disabled={submitting}
          onClick={() => void signIn(QUICK_ADMIN)}
          className="solar-btn-primary mt-8 w-full"
        >
          {submitting ? "Signing in..." : "Sign in as admin (one tap)"}
        </button>

        <div className="my-6 flex items-center gap-3 text-xs uppercase tracking-wide text-[var(--muted)]">
          <span className="h-px flex-1 bg-[var(--border)]" />
          or sign in manually
          <span className="h-px flex-1 bg-[var(--border)]" />
        </div>

        <label className="block text-sm font-medium">
          Username
          <input
            className="solar-input"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
          />
        </label>

        <label className="mt-4 block text-sm font-medium">
          Password
          <input
            type="password"
            className="solar-input"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
          />
        </label>

        {error ? (
          <div className="mt-4">
            <ErrorBanner message={error} />
          </div>
        ) : null}

        <button
          type="submit"
          disabled={submitting}
          className="solar-btn-secondary mt-6 w-full"
        >
          {submitting ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </div>
  );
}
