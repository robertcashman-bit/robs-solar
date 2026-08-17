type AuthLoadingShellProps = {
  /** When true, auth already finished with no session — we are navigating to login. */
  redirecting?: boolean;
};

export function AuthLoadingShell({ redirecting = false }: AuthLoadingShellProps) {
  const label = redirecting ? "Redirecting to sign in" : "Loading session";
  const text = redirecting ? "Redirecting to sign in…" : "Loading session…";

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-400 to-teal-600 text-white shadow-lg">
          <span className="h-5 w-5 animate-pulse rounded-full bg-white/80" aria-hidden="true" />
        </div>
        <p className="text-sm text-[var(--muted)]" role="status" aria-label={label}>
          {text}
        </p>
      </div>
    </div>
  );
}
