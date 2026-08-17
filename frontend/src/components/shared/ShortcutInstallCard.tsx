"use client";

import {
  ROBS_FINANCE_LOGIN_URL,
  ROBS_FINANCE_MAC_INSTALLER,
  ROBS_FINANCE_ORIGIN,
  ROBS_FINANCE_WINDOWS_INSTALLER,
  ROBS_FINANCE_WINDOWS_SHORTCUT,
} from "@/lib/hosted";

const MAC_INSTALL = `curl -fsSL ${ROBS_FINANCE_ORIGIN}${ROBS_FINANCE_MAC_INSTALLER} | bash`;
const WINDOWS_INSTALL = `irm ${ROBS_FINANCE_ORIGIN}${ROBS_FINANCE_WINDOWS_INSTALLER} | iex`;

export function ShortcutInstallCard() {
  return (
    <section
      className="mt-6 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 text-left text-sm"
      aria-labelledby="login-shortcut-heading"
    >
      <h2 id="login-shortcut-heading" className="font-semibold">
        Put Rob&apos;s Finance on your Desktop
      </h2>
      <p className="mt-1 text-[var(--muted)]">
        The shortcut opens the live sign-in page and emails you a new 6-digit code.
      </p>
      <ul className="mt-3 list-inside list-disc space-y-2 text-[var(--muted)]">
        <li>
          <strong className="text-[var(--foreground)]">Windows:</strong>{" "}
          <a
            href={ROBS_FINANCE_WINDOWS_SHORTCUT}
            download="Robs Finance.url"
            className="text-[var(--accent)] hover:underline"
          >
            Download the Desktop shortcut
          </a>
          , or in PowerShell:
          <pre className="mt-2 overflow-x-auto rounded-lg bg-[var(--background)] p-2 text-xs text-[var(--foreground)]">
            {WINDOWS_INSTALL}
          </pre>
        </li>
        <li>
          <strong className="text-[var(--foreground)]">Mac:</strong> paste this in Terminal:
          <pre className="mt-2 overflow-x-auto rounded-lg bg-[var(--background)] p-2 text-xs text-[var(--foreground)]">
            {MAC_INSTALL}
          </pre>
        </li>
        <li>
          <strong className="text-[var(--foreground)]">Phone:</strong> open{" "}
          <a
            href={ROBS_FINANCE_LOGIN_URL}
            className="text-[var(--accent)] hover:underline"
            target="_blank"
            rel="noreferrer"
          >
            {ROBS_FINANCE_ORIGIN}
          </a>{" "}
          → Share / menu → Add to Home Screen.
        </li>
      </ul>
    </section>
  );
}
