"use client";

import { useCallback, useState } from "react";

import { ErrorBanner, SuccessBanner } from "@/components/shared/Banners";
import { UkDateInput } from "@/components/shared/UkDateInput";
import { apiClient } from "@/lib/api-client";
import { notifyFinanceChanged } from "@/lib/finance-events";
import { formatReconFlagLabel } from "@/lib/finance-labels";
import { formatGbp } from "@/lib/money";
import { useFinanceReload } from "@/lib/use-finance-reload";

type HistoryPreview = {
  scope: string;
  uncategorised_count: number;
  insufficient?: boolean;
  explanation?: string;
  income?: { amount_gbp: number; confidence: string; insufficient_data: boolean };
  lines: Array<{
    category: string;
    amount_gbp: number;
    confidence: string;
    insufficient_data: boolean;
    source_note: string;
  }>;
  one_offs?: Array<{
    category: string;
    amount_gbp: number;
    txn_count: number;
    source_note: string;
  }>;
};

type RecurringRule = {
  id: number;
  description: string;
  amount_gbp: number;
  cadence: string;
  status: string;
  scope: string;
};

type SinkingFund = {
  id: number;
  name: string;
  target_gbp: number;
  saved_gbp: number;
  due_on: string;
  remaining_gbp: number;
  months_left: number;
  monthly_contribution_gbp: number;
  formula: string;
  scope: string;
};

export function FinanceIntegrityPanel({
  canEdit,
  defaultScope = "personal",
}: {
  canEdit: boolean;
  defaultScope?: "personal" | "business";
}) {
  const [scope, setScope] = useState<"personal" | "business">(defaultScope);
  const [preview, setPreview] = useState<HistoryPreview | null>(null);
  const [recurring, setRecurring] = useState<RecurringRule[]>([]);
  const [funds, setFunds] = useState<SinkingFund[]>([]);
  const [recon, setRecon] = useState<{ flags?: Array<{ account_name?: string; status?: string; kind?: string }> } | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [fundForm, setFundForm] = useState({ name: "", target_gbp: "", due_on: "" });

  const load = useCallback(async () => {
    try {
      const [history, rules, sinking, flags] = await Promise.all([
        apiClient.get<HistoryPreview>(`/finance/budgets/from-history?scope=${scope}`),
        apiClient.get<RecurringRule[]>(`/finance/recurring?scope=${scope}`),
        apiClient.get<SinkingFund[]>(`/finance/sinking-funds?scope=${scope}`),
        apiClient.get<{ flags?: Array<{ account_name?: string; status?: string; kind?: string }> }>(
          "/finance/reconciliation",
        ),
      ]);
      setPreview(history);
      setRecurring(rules);
      setFunds(sinking);
      setRecon(flags);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load integrity tools");
    }
  }, [scope]);

  useFinanceReload(load, true);

  async function generate() {
    if (!canEdit || busy) return;
    setBusy(true);
    try {
      await apiClient.post("/finance/budgets/from-history", {
        scope,
        activate: true,
        name: `${scope === "personal" ? "Personal" : "Business"} history budget`,
      });
      setStatus(`Created and activated the ${scope} history budget from stored transactions.`);
      notifyFinanceChanged();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate history budget");
    } finally {
      setBusy(false);
    }
  }

  async function detectRecurring() {
    if (!canEdit || busy) return;
    setBusy(true);
    try {
      const proposed = await apiClient.post<RecurringRule[]>(`/finance/recurring/detect?scope=${scope}`);
      setStatus(`Proposed ${proposed.length} recurring rule(s). Confirm or reject each one.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Recurring detection failed");
    } finally {
      setBusy(false);
    }
  }

  async function setRule(id: number, action: "confirm" | "reject") {
    await apiClient.post(`/finance/recurring/${id}/${action}`);
    notifyFinanceChanged();
    await load();
  }

  async function addFund(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || busy) return;
    setBusy(true);
    try {
      await apiClient.post("/finance/sinking-funds", {
        scope,
        name: fundForm.name,
        target_gbp: Number(fundForm.target_gbp),
        due_on: fundForm.due_on,
      });
      setFundForm({ name: "", target_gbp: "", due_on: "" });
      setStatus("Sinking fund saved. Monthly contribution is remaining ÷ months left.");
      notifyFinanceChanged();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save sinking fund");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap gap-2">
        {(["personal", "business"] as const).map((item) => (
          <button
            key={item}
            type="button"
            className={item === scope ? "solar-btn-primary" : "solar-btn-ghost"}
            onClick={() => setScope(item)}
          >
            {item === "personal" ? "Personal budget" : "Business budget"}
          </button>
        ))}
      </div>
      {error ? <ErrorBanner message={error} /> : null}
      {status ? <SuccessBanner message={status} /> : null}

      <div className="solar-card space-y-3">
        <h2 className="text-lg font-semibold">Generate budget from history</h2>
        <p className="text-sm text-[var(--muted)]">
          Uses stored {scope} transactions only. Missing months are dropped and weights
          renormalized. Uncategorised rows stay insufficient — they are not guessed.
        </p>
        {preview ? (
          <p className="text-sm text-[var(--muted)]">
            Income {preview.income?.insufficient_data ? "insufficient" : formatGbp(preview.income?.amount_gbp)}{" "}
            ({preview.income?.confidence}). {preview.uncategorised_count} uncategorised
            transaction(s). {preview.lines.length} categorised line(s).
          </p>
        ) : null}
        <ul className="space-y-1 text-sm">
          {(preview?.lines || []).map((line) => (
            <li key={line.category}>
              {line.category}:{" "}
              {line.insufficient_data ? "Insufficient data" : formatGbp(line.amount_gbp)}{" "}
              <span className="text-[var(--muted)]">
                {line.confidence}
                {line.source_note ? ` — ${line.source_note}` : ""}
              </span>
            </li>
          ))}
        </ul>
        {(preview?.one_offs || []).length > 0 ? (
          <div className="space-y-1 text-sm">
            <p className="font-medium">One-offs (excluded from typical)</p>
            <ul className="space-y-1">
              {(preview?.one_offs || []).map((item) => (
                <li key={item.category}>
                  {item.category}: {formatGbp(item.amount_gbp)}{" "}
                  <span className="text-[var(--muted)]">
                    {item.txn_count} txn(s) — {item.source_note}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {canEdit ? (
          <button type="button" className="solar-btn-primary" onClick={() => void generate()} disabled={busy}>
            {busy ? "Working…" : `Create ${scope} history budget`}
          </button>
        ) : null}
      </div>

      <div className="solar-card space-y-3">
        <h2 className="text-lg font-semibold">Recurring (proposed only)</h2>
        <p className="text-sm text-[var(--muted)]">
          Unconfirmed rules are not treated as recurring spend.
        </p>
        {canEdit ? (
          <button type="button" className="solar-btn-ghost" onClick={() => void detectRecurring()} disabled={busy}>
            Detect recurring
          </button>
        ) : null}
        <ul className="space-y-2 text-sm">
          {recurring.map((rule) => (
            <li key={rule.id} className="flex flex-wrap items-center justify-between gap-2">
              <span>
                {rule.description} {formatGbp(rule.amount_gbp)} / {rule.cadence} — {rule.status}
              </span>
              {canEdit && rule.status === "proposed" ? (
                <span className="flex gap-2">
                  <button type="button" className="solar-btn-ghost" onClick={() => void setRule(rule.id, "confirm")}>
                    Confirm
                  </button>
                  <button type="button" className="solar-btn-ghost" onClick={() => void setRule(rule.id, "reject")}>
                    Reject
                  </button>
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      </div>

      <div className="solar-card space-y-3">
        <h2 className="text-lg font-semibold">Sinking funds</h2>
        <p className="text-sm text-[var(--muted)]">
          You set the target and due date. Monthly contribution is remaining ÷ months left.
          No default holiday amounts.
        </p>
        <ul className="space-y-1 text-sm">
          {funds.map((fund) => (
            <li key={fund.id}>
              {fund.name}: {formatGbp(fund.monthly_contribution_gbp)} / month ({fund.formula}) due {fund.due_on}
            </li>
          ))}
        </ul>
        {canEdit ? (
          <form onSubmit={(event) => void addFund(event)} className="grid gap-2 sm:grid-cols-4">
            <input
              className="solar-input"
              placeholder="Name"
              value={fundForm.name}
              onChange={(event) => setFundForm({ ...fundForm, name: event.target.value })}
              required
            />
            <input
              className="solar-input"
              placeholder="Target £"
              value={fundForm.target_gbp}
              onChange={(event) => setFundForm({ ...fundForm, target_gbp: event.target.value })}
              required
            />
            <UkDateInput
              value={fundForm.due_on}
              onChange={(due_on) => setFundForm({ ...fundForm, due_on })}
              required
            />
            <button type="submit" className="solar-btn-primary" disabled={busy}>
              Add fund
            </button>
          </form>
        ) : null}
      </div>

      <div className="solar-card space-y-3">
        <h2 className="text-lg font-semibold">Reconciliation flags</h2>
        <p className="text-sm text-[var(--muted)]">
          Confirmed balances are never auto-edited to match the ledger.
        </p>
        <ul className="space-y-1 text-sm">
          {(recon?.flags || []).length === 0 ? (
            <li>No discrepancy flags. Opening-balance history may still be insufficient.</li>
          ) : (
            (recon?.flags || []).map((flag, index) => (
              <li key={`${flag.account_name}-${index}`}>
                {flag.account_name}: {formatReconFlagLabel(flag.kind ?? "", flag.status ?? "")}
              </li>
            ))
          )}
        </ul>
      </div>
    </section>
  );
}
