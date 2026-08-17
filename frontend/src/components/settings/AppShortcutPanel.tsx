"use client";

import { ShortcutInstallCard } from "@/components/shared/ShortcutInstallCard";

export function AppShortcutPanel() {
  return (
    <section className="solar-card space-y-4" id="app-shortcut" aria-labelledby="app-shortcut-heading">
      <div>
        <h2 id="app-shortcut-heading" className="text-lg font-semibold">
          App shortcut
        </h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Put Rob&apos;s Finance on the Desktop, Dock, or your phone home screen. The shortcut
          opens sign-in and emails a new 6-digit code.
        </p>
      </div>

      <ShortcutInstallCard />

      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 text-sm">
        <p className="font-medium">This Mac with the All repo</p>
        <ul className="mt-2 list-inside list-disc space-y-1 text-[var(--muted)]">
          <li>
            Double-click <strong className="text-[var(--foreground)]">Install Rob&apos;s Finance</strong>{" "}
            or <strong className="text-[var(--foreground)]">RobsFinance.app</strong> when the All repo
            is present. That rebuilds the local app, puts it on the Desktop, and pins the Dock.
          </li>
          <li>
            Opening <strong className="text-[var(--foreground)]">Rob Finance App</strong> in Cursor
            also restores those shortcuts.
          </li>
        </ul>
      </div>
    </section>
  );
}
