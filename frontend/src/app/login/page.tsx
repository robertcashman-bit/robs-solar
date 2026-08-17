"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ErrorBanner } from "@/components/shared/Banners";
import { PageLoading } from "@/components/shared/PageLoading";
import { WalletIcon } from "@/components/shared/icons";
import { useAuth } from "@/lib/auth-context";
import { readLastEmail, rememberLastEmail } from "@/lib/last-email";

type Stage = "email" | "otp" | "password";

export default function LoginPage() {
  const router = useRouter();
  const { login, requestMagicCode, verifyMagicCode, user, loading } = useAuth();
  const [stage, setStage] = useState<Stage>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setEmail(readLastEmail());
  }, []);

  useEffect(() => {
    if (!loading && user) {
      router.replace("/");
    }
  }, [loading, user, router]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <div className="w-full max-w-md">
          <PageLoading label="Checking session" rows={1} />
        </div>
      </div>
    );
  }

  if (user) {
    return null;
  }

  const handleSendCode = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    const trimmed = email.trim().toLowerCase();
    try {
      await requestMagicCode(trimmed);
      rememberLastEmail(trimmed);
      setEmail(trimmed);
      setStage("otp");
    } catch (sendError) {
      setError(sendError instanceof Error ? sendError.message : "Could not send login code");
    } finally {
      setSubmitting(false);
    }
  };

  const handleVerifyCode = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await verifyMagicCode(email.trim().toLowerCase(), code.trim());
      rememberLastEmail(email);
      router.replace("/");
    } catch (verifyError) {
      setError(verifyError instanceof Error ? verifyError.message : "Verification failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handlePasswordSubmit = async (event: FormEvent) => {
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
    <div className="flex min-h-screen items-center justify-center px-4 py-8">
      <div
        className="w-full max-w-md rounded-2xl border border-[var(--border)] bg-[var(--surface-elevated)] p-6 shadow-xl backdrop-blur-xl sm:p-8"
        style={{ boxShadow: "var(--shadow-lg)" }}
      >
        <div className="flex flex-col items-center text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-400 to-teal-600 text-white shadow-lg">
            <WalletIcon size={28} />
          </div>
          <p className="mt-4 text-xs font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
            Rob&apos;s Finance
          </p>
          <h1 id="login-heading" className="mt-1 text-2xl font-bold">
            Sign in
          </h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            We&rsquo;ll email a one-time magic code. Password sign-in stays available as a fallback.
          </p>
        </div>

        {stage === "email" ? (
          <form
            onSubmit={(event) => void handleSendCode(event)}
            className="mt-8"
            aria-labelledby="login-heading"
          >
            <label className="block text-sm font-medium">
              Email
              <input
                type="email"
                className="solar-input"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="username"
                required
              />
            </label>
            {error ? (
              <div className="mt-4">
                <ErrorBanner message={error} />
              </div>
            ) : null}
            <button type="submit" disabled={submitting} className="solar-btn-primary mt-6 w-full">
              {submitting ? "Sending code…" : "Email me a magic code"}
            </button>
            <button
              type="button"
              className="mt-3 w-full text-sm font-semibold text-[var(--muted)] underline hover:text-[var(--foreground)]"
              onClick={() => {
                setStage("password");
                setError(null);
              }}
            >
              Use password instead
            </button>
          </form>
        ) : null}

        {stage === "otp" ? (
          <form
            onSubmit={(event) => void handleVerifyCode(event)}
            className="mt-8"
            aria-labelledby="login-heading"
          >
            <div className="rounded-xl border border-emerald-300/50 bg-emerald-50/90 px-4 py-3 text-sm text-emerald-900 dark:border-emerald-800/50 dark:bg-emerald-950/40 dark:text-emerald-200">
              <p className="font-medium">Check your email for a login code.</p>
              <p className="mt-1 text-xs">
                We sent a 6-digit code to <strong>{email}</strong>. It may take a minute to arrive.
              </p>
            </div>
            <label className="mt-4 block text-sm font-medium">
              Magic code
              <input
                className="solar-input text-center text-lg tracking-[0.3em]"
                value={code}
                onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="123456"
                required
              />
            </label>
            {error ? (
              <div className="mt-4">
                <ErrorBanner message={error} />
              </div>
            ) : null}
            <button type="submit" disabled={submitting} className="solar-btn-primary mt-6 w-full">
              {submitting ? "Verifying…" : "Sign in"}
            </button>
            <button
              type="button"
              className="mt-3 w-full text-sm font-semibold text-[var(--muted)] underline hover:text-[var(--foreground)]"
              onClick={() => {
                setStage("email");
                setCode("");
                setError(null);
              }}
            >
              Use a different email
            </button>
          </form>
        ) : null}

        {stage === "password" ? (
          <form
            onSubmit={(event) => void handlePasswordSubmit(event)}
            className="mt-8"
            aria-labelledby="login-heading"
          >
            <label className="block text-sm font-medium">
              Username
              <input
                className="solar-input"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
                required
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
                required
              />
            </label>
            {error ? (
              <div className="mt-4">
                <ErrorBanner message={error} />
              </div>
            ) : null}
            <button type="submit" disabled={submitting} className="solar-btn-primary mt-6 w-full">
              {submitting ? "Signing in…" : "Sign in"}
            </button>
            <button
              type="button"
              className="mt-3 w-full text-sm font-semibold text-[var(--muted)] underline hover:text-[var(--foreground)]"
              onClick={() => {
                setStage("email");
                setError(null);
              }}
            >
              Use magic code instead
            </button>
          </form>
        ) : null}

        <p className="mt-6 text-center text-xs text-[var(--muted)]">
          Add this sign-in page to your Dock or Home Screen from the browser share menu.
        </p>
        <p className="mt-3 text-center text-xs text-[var(--muted)]">
          By signing in you agree to our{" "}
          <Link href="/terms" className="underline hover:text-[var(--foreground)]">
            terms
          </Link>{" "}
          and{" "}
          <Link href="/privacy" className="underline hover:text-[var(--foreground)]">
            privacy policy
          </Link>
          .
        </p>
      </div>
    </div>
  );
}
