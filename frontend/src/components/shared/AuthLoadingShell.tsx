import { AppShell } from "@/components/shared/AppShell";

export function AuthLoadingShell() {
  return (
    <AppShell>
      <p className="text-sm text-[var(--muted)]" role="status" aria-label="Loading session">
        Loading session…
      </p>
    </AppShell>
  );
}
