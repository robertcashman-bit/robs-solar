"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ErrorBanner } from "@/components/shared/Banners";
import { SunIcon } from "@/components/shared/icons";
import { useAuth } from "@/lib/auth-context";

export default function LoginPage() {
  const router = useRouter();
  const { login, user, loading } = useAuth();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("change-me-admin");
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

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(username, password);
      router.replace("/");
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form
        onSubmit={(event) => void handleSubmit(event)}
        className="w-full max-w-md rounded-2xl border border-[var(--border)] bg-[var(--surface-elevated)] p-8 shadow-xl backdrop-blur-xl"
        style={{ boxShadow: "var(--shadow-lg)" }}
      >
        <div className="flex flex-col items-center text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-400 to-orange-500 text-white shadow-lg">
            <SunIcon size={28} />
          </div>
          <p className="mt-4 text-xs font-semibold uppercase tracking-wider text-[var(--solar-dark)]">
            Rob&apos;s Solar
          </p>
          <h1 className="mt-1 text-2xl font-bold">Sign in</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">Local auth for monitoring and control.</p>
        </div>

        <label className="mt-8 block text-sm font-medium">
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
          className="solar-btn-primary mt-6 w-full"
        >
          {submitting ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </div>
  );
}
