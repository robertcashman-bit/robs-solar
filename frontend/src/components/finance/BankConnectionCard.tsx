"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import {
  connectionStatusClass,
  connectionStatusLabel,
  formatLastSynced,
} from "@/lib/bank-connections";
import { apiClient } from "@/lib/api-client";
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
  onFundingCircleSaved?: () => void;
};

export function BankConnectionCard({
  connection,
  writable,
  busy,
  personalProvider = "enable_banking",
  onConnect,
  onDisconnect,
  onSync,
  onFundingCircleSaved,
}: BankConnectionCardProps) {
  const connected = connection.status === "connected" || connection.status === "manual";
  const isLunchFlowOpenBanking =
    connection.method === "open_banking" && personalProvider === "lunch_flow";
  const canConnect =
    writable &&
    connection.status !== "not_configured" &&
    (connection.status === "not_connected" ||
      connection.status === "awaiting_login" ||
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

  // QuickFile-only matches need no manual form (would double-count). Manual /
  // not_connected still need balance entry.
  const showFundingCircleForm =
    writable &&
    connection.id === "funding_circle" &&
    connection.method === "manual" &&
    connection.institution !== "QuickFile";

  const [balance, setBalance] = useState(
    connection.status === "manual" && connection.balance_gbp > 0
      ? String(connection.balance_gbp)
      : "",
  );
  const [rate, setRate] = useState("");
  const [minPayment, setMinPayment] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formMessage, setFormMessage] = useState<string | null>(null);

  async function saveFundingCircle(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setFormError(null);
    setFormMessage(null);
    try {
      const balanceGbp = Number(balance);
      const ratePct = Number(rate || "0");
      const minPay = Number(minPayment || "0");
      if (!Number.isFinite(balanceGbp) || balanceGbp < 0) {
        throw new Error("Enter a valid outstanding balance.");
      }
      const existing = (await apiClient.get<
        Array<{ id: number; name: string; scope: string }>
      >("/finance/liabilities?scope=business")).find((row) =>
        row.name.toLowerCase().includes("funding circle"),
      );
      if (existing) {
        await apiClient.put(`/finance/liabilities/${existing.id}`, {
          balance_gbp: balanceGbp,
          interest_rate_pct: ratePct,
          minimum_payment_gbp: minPay,
        });
        setFormMessage("Funding Circle balance updated.");
      } else {
        await apiClient.post("/finance/liabilities", {
          scope: "business",
          name: "Funding Circle",
          debt_type: "business_loan",
          balance_gbp: balanceGbp,
          interest_rate_pct: ratePct,
          minimum_payment_gbp: minPay,
          notes: "manual-funding-circle",
        });
        setFormMessage("Funding Circle loan saved.");
      }
      onFundingCircleSaved?.();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not save Funding Circle loan");
    } finally {
      setSaving(false);
    }
  }

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
          <Link href="/finance/connect#open-banking-setup" className="text-sm underline">
            Open Banking setup →
          </Link>
        )
      ) : null}

      {showFundingCircleForm ? (
        <form onSubmit={(e) => void saveFundingCircle(e)} className="mt-auto space-y-2">
          <p className="text-xs text-[var(--muted)]">
            No live API — log into{" "}
            <a
              href="https://borrower.fundingcircle.com/"
              target="_blank"
              rel="noreferrer"
              className="underline"
            >
              Funding Circle
            </a>{" "}
            and enter the outstanding balance below.
          </p>
          <div className="grid grid-cols-2 gap-2">
            <label className="flex flex-col gap-1 text-xs">
              Balance £
              <input
                className="solar-input text-sm"
                type="number"
                min="0"
                step="0.01"
                required
                value={balance}
                onChange={(e) => setBalance(e.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs">
              Rate %
              <input
                className="solar-input text-sm"
                type="number"
                min="0"
                step="0.01"
                value={rate}
                onChange={(e) => setRate(e.target.value)}
                placeholder="0"
              />
            </label>
          </div>
          <label className="flex flex-col gap-1 text-xs">
            Min payment £ (optional)
            <input
              className="solar-input text-sm"
              type="number"
              min="0"
              step="0.01"
              value={minPayment}
              onChange={(e) => setMinPayment(e.target.value)}
              placeholder="0"
            />
          </label>
          {formError ? <p className="text-xs text-red-700 dark:text-red-300">{formError}</p> : null}
          {formMessage ? (
            <p className="text-xs text-emerald-800 dark:text-emerald-200">{formMessage}</p>
          ) : null}
          <button type="submit" className="solar-btn-primary text-sm" disabled={busy || saving}>
            {saving
              ? "Saving…"
              : connection.status === "manual"
                ? "Update Funding Circle"
                : "Save Funding Circle loan"}
          </button>
        </form>
      ) : null}

      {writable && !showFundingCircleForm ? (
        <div className="mt-auto flex flex-wrap gap-2">
          {canConnect ? (
            <button type="button" className="solar-btn-primary text-sm" disabled={busy} onClick={onConnect}>
              {isLunchFlowOpenBanking ? "Authorize at Lunch Flow" : "Connect"}
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
        </div>
      ) : null}
    </article>
  );
}
