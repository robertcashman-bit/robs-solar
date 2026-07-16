import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-4 py-16 text-center">
      <p className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">404</p>
      <h1 className="mt-2 text-2xl font-semibold text-[var(--foreground)]">Page not found</h1>
      <p className="mt-2 max-w-md text-sm text-[var(--muted)]">
        That route does not exist. Head back to finance overview or energy dashboard.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <Link href="/" className="solar-btn-primary">
          Finance overview
        </Link>
        <Link href="/energy" className="solar-btn-secondary">
          Energy dashboard
        </Link>
      </div>
    </div>
  );
}
