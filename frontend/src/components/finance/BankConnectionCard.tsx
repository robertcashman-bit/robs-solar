"use client";

import Link from "next/link";

import {
  connectionStatusClass,
  connectionStatusLabel,
  formatLastSynced,
} from "@/lib/bank-connections";
import type { BankConnectionItem } from "@/lib/finance-schemas";
import { formatGbp } from "@/lib/money";

type BankConnectionCardProps = {
  connection: BankConnectionItem;
  writable: boolean;
  busy: boolean;
  personalProvider?: "enable_banking" | "lunch_flow";
  onConnect: () => void;
  onDisconnect: () => void;
  onSync: () => void;
};

export function BankConnectionCard({
  connection,
  writable,
  busy,
  personalProvider = "enable_banking",
  onConnect,
  onDisconnect,
  onSync,
}: BankConnectionCardProps) {
  const connected = connection.status === "connected" || connection.status === "manual";
  const canConnect =
    writable &&
    (connection.status === "not_connected" ||
      connection.status === "awaiting_login" ||
      connection.status === "not_configured" ||
      connection.status === "needs_reconnection");
  // Lunch Flow connections are managed at lunchflow.app — the backend cannot
  // disconnect them, so offering the button here would be dishonest.
  const canDisconnect =
    writable &&
    connection.method === "open_banking" &&
    personalProvider !== "lunch_flow" &&
    connected;
  const canSync =
    writable &&
    (connection.method === "open_banking" || connection.method === "quickfile") &&
    connection.status !== "not_configured";

  return (
    <article className="flex flex-col gap-4 rounded-xl border border-[var(--border)] p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[var(--surface-sunken)] text-lg font-semibold"
            aria-hidden
          >
            {connection.label.charAt(0)}
          </div>
          <div>
            <h3 className="font-semibold">{connection.label}</h3>
            <p className="text-xs text-[var(--muted)]">
              {connection.method === "open_banking"
                ? personalProvider === "lunch_flow"
                  ? "Lunch Flow"
                  : "Open Banking"
                : connection.method === "quickfile"
                  ? "QuickFile"
                  : "Manual balance"}
            </p>
          </div>
        </div>
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-medium ${connectionStatusClass(connection.status)}`}
        >
          {connectionStatusLabel(connection.status)}
        </span>
      </div>

      <p className="text-sm text-[var(--muted)]">{connection.status_message}</p>

      <dl className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <dt className="text-xs text-[var(--muted)]">Last synced</dt>
          <dd>{formatLastSynced(connection.last_sync_at)}</dd>
        </div>
        {connected && connection.account_count > 0 ? (
          <div>
            <dt className="text-xs text-[var(--muted)]">Balance</dt>
            <dd>{formatGbp(connection.balance_gbp)}</dd>
          </div>
        ) : null}
      </dl>

      {connection.status === "not_configured" ? (
        personalProvider === "lunch_flow" ? (
          <p className="text-sm text-[var(--muted)]">Add your Lunch Flow API key above.</p>
        ) : (
          <Link href="/finance/open-banking/settings" className="text-sm underline">
            Open Banking Settings →
          </Link>
        )
      ) : null}

      {writable ? (
        <div className="mt-auto flex flex-wrap gap-2">
          {canConnect ? (
            <button type="button" className="solar-btn-primary text-sm" disabled={busy} onClick={onConnect}>
              Connect
            </button>
          ) : null}
          {canSync ? (
            <button type="button" className="solar-btn-secondary text-sm" disabled={busy} onClick={onSync}>
              Sync now
            </button>
          ) : null}
          {canDisconnect ? (
            <button type="button" className="solar-btn-ghost text-sm" disabled={busy} onClick={onDisconnect}>
              Disconnect
            </button>
          ) : null}
          {connection.id === "funding_circle" && connection.status === "not_connected" ? (
            <Link href="/finance/debts" className="solar-btn-secondary text-sm">
              Add manual loan
            </Link>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
