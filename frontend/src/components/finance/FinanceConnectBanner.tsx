"use client";

import Link from "next/link";

import type { BankConnectionItem } from "@/lib/finance-schemas";

type FinanceConnectBannerProps = {
  connections: BankConnectionItem[];
  obConfigured: boolean;
  obReady?: boolean | null;
  lunchFlowActive?: boolean;
};

export function FinanceConnectBanner({
  connections,
  obConfigured,
  obReady = null,
  lunchFlowActive = false,
}: FinanceConnectBannerProps) {
  // Personal banks are handled by Lunch Flow. When it is configured, the legacy
  // Enable Banking / Open Banking activation prompts are obsolete noise, so we
  // suppress this banner entirely and let the Connect banks page manage links.
  if (lunchFlowActive) {
    return null;
  }

  const openBanking = connections.filter((c) => c.method === "open_banking");
  const needsConnect = openBanking.some(
    (c) => c.status === "not_connected" || c.status === "needs_reconnection",
  );

  if (!needsConnect && obConfigured && obReady !== false) {
    return null;
  }

  if (obConfigured && obReady === false) {
    return (
      <section className="rounded-2xl border border-amber-400/40 bg-amber-500/10 px-4 py-4 sm:px-5">
        <h2 className="text-base font-semibold text-amber-950 dark:text-amber-100">
          Open Banking needs activation before you can connect banks
        </h2>
        <p className="mt-2 text-sm text-amber-950/90 dark:text-amber-100/90">
          Credentials are saved, but Enable Banking has not activated the app yet. An admin must
          complete activation in the Enable Banking Control Panel, then use{" "}
          <strong>Connect banks</strong> to link Lloyds, MBNA and Virgin Money.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <a
            href="https://enablebanking.com/cp/applications"
            target="_blank"
            rel="noopener noreferrer"
            className="solar-btn-primary text-sm"
          >
            Enable Banking Control Panel
          </a>
          <Link href="/finance/connect" className="solar-btn-secondary text-sm">
            Connect banks →
          </Link>
        </div>
      </section>
    );
  }

  if (!obConfigured) {
    return (
      <section className="rounded-2xl border border-amber-400/40 bg-amber-500/10 px-4 py-4 sm:px-5">
        <h2 className="text-base font-semibold text-amber-950 dark:text-amber-100">
          Connect your banks to see live balances
        </h2>
        <p className="mt-2 text-sm text-amber-950/90 dark:text-amber-100/90">
          Personal accounts (Lloyds, MBNA, Virgin Money) need a one-time Open Banking setup, then
          you connect each bank on the{" "}
          <strong>Connect banks</strong> page — use the menu item with the wallet icon.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Link href="/finance/open-banking/settings" className="solar-btn-secondary text-sm">
            Open Banking Settings (admin, once)
          </Link>
          <Link href="/finance/connect" className="solar-btn-primary text-sm">
            Connect banks →
          </Link>
        </div>
      </section>
    );
  }

  const disconnected = openBanking.filter(
    (c) => c.status === "not_connected" || c.status === "needs_reconnection",
  );

  return (
    <section className="rounded-2xl border border-sky-400/35 bg-sky-500/10 px-4 py-4 sm:px-5">
      <h2 className="text-base font-semibold text-sky-950 dark:text-sky-100">
        Connect your personal banks for live data
      </h2>
      <p className="mt-2 text-sm text-sky-950/90 dark:text-sky-100/90">
        Alerts and balances work best when Lloyds, MBNA and Virgin Money are linked. Go to{" "}
        <strong>Connect banks</strong> in the menu (wallet icon, near the top), press{" "}
        <strong>Connect</strong> on each card, and sign in on your bank&apos;s website.
      </p>
      {disconnected.length ? (
        <p className="mt-2 text-sm font-medium text-sky-950 dark:text-sky-100">
          Still to connect: {disconnected.map((c) => c.label).join(", ")}
        </p>
      ) : null}
      <Link href="/finance/connect" className="solar-btn-primary mt-3 inline-flex text-sm">
        Open Connect banks →
      </Link>
    </section>
  );
}
