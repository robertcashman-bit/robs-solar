import Link from "next/link";
import type { ReactNode } from "react";

type LegalPageLayoutProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
};

export function LegalPageLayout({ title, subtitle, children }: LegalPageLayoutProps) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-[var(--border)] bg-[var(--surface-elevated)]/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-2xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <Link
            href="/login"
            className="text-sm font-medium text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
          >
            ← Back to sign in
          </Link>
          <Link
            href="/"
            className="text-sm font-medium text-emerald-700 dark:text-emerald-400"
          >
            Dashboard
          </Link>
        </div>
      </header>
      <main className="mx-auto w-full max-w-2xl flex-1 space-y-6 px-4 py-8 sm:px-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
          {subtitle ? <p className="mt-1 text-sm text-[var(--muted)]">{subtitle}</p> : null}
        </div>
        <div className="space-y-4 text-sm leading-relaxed text-[var(--foreground)]">{children}</div>
        <footer className="border-t border-[var(--border)] pt-6 text-xs text-[var(--muted)]">
          <nav aria-label="Legal" className="flex flex-wrap gap-4">
            <Link href="/privacy" className="underline hover:text-[var(--foreground)]">
              Privacy policy
            </Link>
            <Link href="/terms" className="underline hover:text-[var(--foreground)]">
              Terms of use
            </Link>
          </nav>
        </footer>
      </main>
    </div>
  );
}
