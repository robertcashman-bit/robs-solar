"use client";

const HOSTED_URL = "https://robs-solar.vercel.app";

export function AppShortcutPanel() {
  return (
    <section className="solar-card space-y-4" id="app-shortcut" aria-labelledby="app-shortcut-heading">
      <div>
        <h2 id="app-shortcut-heading" className="text-lg font-semibold">
          App shortcut
        </h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Put Rob&apos;s Finance back on the Mac Dock, Desktop, or your phone home screen.
        </p>
      </div>

      <div className="grid gap-3 text-sm sm:grid-cols-2">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
          <p className="font-medium">Mac Dock and Desktop</p>
          <ul className="mt-2 list-inside list-disc space-y-1 text-[var(--muted)]">
            <li>
              On this Mac, double-click <strong className="text-[var(--foreground)]">Install Rob&apos;s Finance</strong>{" "}
              or <strong className="text-[var(--foreground)]">RobsFinance.app</strong>. That rebuilds the
              app, puts it on the Desktop, and pins the Dock.
            </li>
            <li>
              Opening <strong className="text-[var(--foreground)]">Rob Finance App</strong> in Cursor
              also restores those shortcuts.
            </li>
          </ul>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
          <p className="font-medium">Phone home screen</p>
          <ul className="mt-2 list-inside list-disc space-y-1 text-[var(--muted)]">
            <li>
              <strong className="text-[var(--foreground)]">iPhone (Safari):</strong> open the app URL →
              Share → Add to Home Screen
            </li>
            <li>
              <strong className="text-[var(--foreground)]">Android (Chrome):</strong> open the app URL →
              browser menu → Install app
            </li>
          </ul>
          <p className="mt-3">
            <a href={HOSTED_URL} className="text-[var(--accent)] hover:underline" target="_blank" rel="noreferrer">
              {HOSTED_URL}
            </a>
          </p>
        </div>
      </div>
    </section>
  );
}
