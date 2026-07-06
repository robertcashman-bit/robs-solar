"use client";

import Link from "next/link";

import type { BankConnectionItem } from "@/lib/finance-schemas";

type FinanceConnectBannerProps = {
  connections: BankConnectionItem[];
  obConfigured: boolean;
};

export function FinanceConnectBanner({ connections, obConfigured }: FinanceConnectBannerProps) {
  const openBanking = connections.filter((c) => c.method === "open_banking");
  const needsConnect = openBanking.some(
    (c) => c.status === "not_connected" || c.status === "needs_reconnection",
  );

  if (!needsConnect && obConfigured) {
    return null;
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
