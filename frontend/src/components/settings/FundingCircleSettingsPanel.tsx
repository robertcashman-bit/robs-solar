"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import {
  fundingCircleConfigStatusSchema,
  fundingCircleSyncResultSchema,
  type FundingCircleConfigStatus,
} from "@/lib/finance-schemas";
import { formatGbp } from "@/lib/money";
import { notifyFinanceChanged } from "@/lib/finance-events";

type FundingCircleSettingsPanelProps = {
  readOnly?: boolean;
};

export function FundingCircleSettingsPanel({ readOnly = false }: FundingCircleSettingsPanelProps) {
  const { user, loading: authLoading } = useAuth();
  const [status, setStatus] = useState<FundingCircleConfigStatus | null>(null);
  const [outstanding, setOutstanding] = useState("");
  const [apr, setApr] = useState("");
  const [minimum, setMinimum] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"save" | "import" | null>(null);

  const load = useCallback(async () => {
    if (!user) return;
    try {
      const fcData = await apiClient.get<unknown>("/finance/integrations/funding-circle/status");
      const fc = fundingCircleConfigStatusSchema.parse(fcData);
      setStatus(fc);
      setOutstanding(fc.outstanding_gbp == null ? "" : String(fc.outstanding_gbp));
      setApr(fc.apr_pct ? String(fc.apr_pct) : "");
      setMinimum(fc.minimum_payment_gbp ? String(fc.minimum_payment_gbp) : "");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Funding Circle status");
    }
  }, [user]);

  useEffect(() => {
    if (authLoading || !user) return;
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [authLoading, user, load]);

  async function save() {
    setBusy("save");
    setError(null);
    setMessage(null);
    try {
      const data = await apiClient.put<unknown>("/finance/integrations/funding-circle/settings", {
        outstanding_gbp: outstanding.trim() ? Number(outstanding) : null,
        apr_pct: apr.trim() ? Number(apr) : 0,
        minimum_payment_gbp: minimum.trim() ? Number(minimum) : 0,
        auto_sync: true,
      });
      setStatus(fundingCircleConfigStatusSchema.parse(data));
      setMessage("Funding Circle details saved");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(null);
    }
  }

  async function refreshFromBankFeed() {
    setBusy("import");
    setError(null);
    setMessage(null);
    try {
      const data = await apiClient.post<unknown>("/finance/integrations/funding-circle/sync");
      const parsed = fundingCircleSyncResultSchema.parse(data);
      setMessage(parsed.message);
      notifyFinanceChanged();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not refresh Funding Circle");
    } finally {
      setBusy(null);
    }
  }

  if (authLoading) {
    return <p className="text-sm text-[var(--muted)]">Loading Funding Circle…</p>;
  }

  return (
    <section className="solar-card space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Funding Circle</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          The loan is not in QuickFile, and Funding Circle has no borrower login API.
          Enter the outstanding balance here, or refresh from Funding Circle payments
          already imported via Lunch Flow.
        </p>
      </div>
      {error ? <p className="text-sm text-red-500">{error}</p> : null}
      {message ? <p className="text-sm text-emerald-500">{message}</p> : null}
      {status?.last_sync_at ? (
        <p className="text-sm text-[var(--muted)]">
          Last import {status.last_sync_at.slice(0, 10)}
          {status.outstanding_gbp != null ? ` · Outstanding ${formatGbp(status.outstanding_gbp)}` : ""}
          {status.message ? ` · ${status.message}` : ""}
        </p>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="space-y-1 text-sm">
          <span>Current outstanding (if the bank feed cannot reconstruct it)</span>
          <input
            className="solar-input"
            inputMode="decimal"
            value={outstanding}
            onChange={(event) => setOutstanding(event.target.value)}
            disabled={readOnly}
            placeholder="Optional"
          />
        </label>
        <label className="space-y-1 text-sm">
          <span>APR %</span>
          <input
            className="solar-input"
            inputMode="decimal"
            value={apr}
            onChange={(event) => setApr(event.target.value)}
            disabled={readOnly}
          />
        </label>
        <label className="space-y-1 text-sm">
          <span>Monthly repayment</span>
          <input
            className="solar-input"
            inputMode="decimal"
            value={minimum}
            onChange={(event) => setMinimum(event.target.value)}
            disabled={readOnly}
          />
        </label>
      </div>
      {!readOnly ? (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="solar-btn-primary"
            onClick={() => void refreshFromBankFeed()}
            disabled={busy != null}
          >
            {busy === "import" ? "Refreshing…" : "Refresh from bank feed"}
          </button>
          <button type="button" className="solar-btn-ghost" onClick={() => void save()} disabled={busy != null}>
            {busy === "save" ? "Saving…" : "Save details"}
          </button>
        </div>
      ) : null}
    </section>
  );
}
