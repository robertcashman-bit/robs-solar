"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth-context";
import type { UserInfo } from "@/lib/schemas";

const HARD_REDIRECT_MS = 1500;

/**
 * Gate protected finance pages. Soft-navigates to /login when there is no
 * session, with a hard location fallback so a stuck App Router RSC navigation
 * cannot leave the UI on “Loading session…” forever.
 *
 * Only redirects after auth is *resolved* unauthenticated. A slow /auth/me
 * (cold start) must not look like logout. A cached session user paints the
 * app immediately while /auth/me confirms.
 */
export function useRequireAuth(): {
  user: UserInfo | null;
  loading: boolean;
  /** True while auth is unresolved or we are sending the user to /login. */
  gated: boolean;
  redirecting: boolean;
} {
  const router = useRouter();
  const { user, loading, authResolved } = useAuth();
  const redirecting = authResolved && !user;
  // Have a user (including optimistic cached session) → paint immediately.
  // Only full-screen gate when we have no user yet and auth is still settling.
  const gated = redirecting || (!user && (loading || !authResolved));

  useEffect(() => {
    if (!redirecting) {
      return;
    }
    router.replace("/login");
    const timer = window.setTimeout(() => {
      if (!window.location.pathname.startsWith("/login")) {
        window.location.replace("/login");
      }
    }, HARD_REDIRECT_MS);
    return () => window.clearTimeout(timer);
  }, [redirecting, router]);

  return {
    user,
    loading,
    gated,
    redirecting,
  };
}
