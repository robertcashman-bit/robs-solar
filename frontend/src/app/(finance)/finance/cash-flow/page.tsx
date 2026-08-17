"use client";

import { useCallback, useState } from "react";

import { MetricTile } from "@/components/finance/MetricTile";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner, SuccessBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { apiClient } from "@/lib/api-client";
import { useRequireAuth } from "@/lib/use-require-auth";
import { COMPANY_SHORT, PERSONAL_LEDGER } from "@/lib/finance-branding";
import { notifyFinanceChanged } from "@/lib/finance-events";
import { useFinanceReload } from "@/lib/use-finance-reload";
import { cashflowForecastSchema, type CashflowForecast } from "@/lib/finance-schemas";
import { formatGbp, parseGbp } from "@/lib/money";
import { canWrite } from "@/lib/permissions";

const horizons = [
  { days: 7, label: "7d" },
  { days: 14, label: "14d" },
  { days: 30, label: "30d" },
  { days: 60, label: "60d" },
  { days: 90, label: "90d" },
  { days: 180, label: "6m" },
  { days: 365, label: "12m" },
] as const;
const scopes = ["all", "personal", "business"] as const;
const scenarios = ["conservative", "expected", "optimistic"] as const;

export default function CashFlowPage() {
  const { user, gated, redirecting } = useRequireAuth();
  const [horizon, setHorizon] = useState<number>(30);
  const [scope, setScope] = useState<(typeof scopes)[number]>("all");
  const [scenario, setScenario] = useState<(typeof scenarios)[number]>("expected");
  const [forecast, setForecast] = useState<CashflowForecast | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [form, setForm] = useState({
    label: "",
    amount_gbp: "",
    forecast_date: new Date().toISOString().slice(0, 10),
    entry_type: "bill",
    scope: "personal",
  });

  const load = useCallback(async () => {
    try {
      const query = new URLSearchParams({ horizon: String(horizon) });
      if (scope !== "all") query.set("scope", scope);
      const data = await apiClient.get<unknown>(`/finance/cashflow?${query.toString()}`);
      setForecast(cashflowForecastSchema.parse(data));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load cash flow");
    }
  }, [horizon, scope]);


  useFinanceReload(load, Boolean(user));

  async function addEntry(event: React.FormEvent) {
    event.preventDefault();
    if (!canWrite(user) || saving) return;
    setSaving(true);
    try {
      const amount = parseGbp(form.amount_gbp);
      if (!form.label.trim() || Number.isNaN(amount)) {
        throw new Error("Enter a label and a valid amount");
      }
      await apiClient.post("/finance/cashflow", {
        scope: form.scope,
        forecast_date: form.forecast_date,
        horizon_days: horizon,
        entry_type: form.entry_type,
        label: form.label,
        amount_gbp: amount,
        is_confirmed: false,
        source: "manual",
      });
      setForm({ ...form, label: "", amount_gbp: "" });
      setStatus("Cashflow entry added");
      await load();
      notifyFinanceChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add entry");
    } finally {
      setSaving(false);
    }
  }

  async function removeEntry() {
    if (deleteId == null) return;
    try {
      await apiClient.delete(`/finance/cashflow/${deleteId}`);
      setStatus("Entry removed");
      setDeleteId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete entry");
    }
  }

  if (gated) return <AuthLoadingShell redirecting={redirecting} />;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Cash Flow"
        description="7-day to 12-month forecast with expected income, bills, debt payments, and tax."
        actions={
          <div className="flex flex-wrap gap-2">
            <div className="flex gap-1 rounded-lg border border-[var(--border)] p-1">
              {scopes.map((item) => (
                <button
                  key={item}
                  type="button"
                  className={`rounded-md px-3 py-1 text-sm capitalize ${scope === item ? "bg-emerald-500 text-white" : ""}`}
                  onClick={() => setScope(item)}
                >
                  {item === "personal" ? PERSONAL_LEDGER : item === "business" ? COMPANY_SHORT : "All"}
                </button>
              ))}
            </div>
            <div className="flex gap-1 rounded-lg border border-[var(--border)] p-1">
              {scenarios.map((item) => (
                <button
                  key={item}
                  type="button"
                  className={`rounded-md px-3 py-1 text-sm capitalize ${scenario === item ? "bg-teal-600 text-white" : ""}`}
                  onClick={() => setScenario(item)}
                >
                  {item}
                </button>
              ))}
            </div>
            <div className="flex gap-1 rounded-lg border border-[var(--border)] p-1">
              {horizons.map((item) => (
                <button
                  key={item.days}
                  type="button"
                  className={`rounded-md px-3 py-1 text-sm ${horizon === item.days ? "bg-emerald-500 text-white" : ""}`}
                  onClick={() => setHorizon(item.days)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        }
      />
      {error ? <div className="mt-4"><ErrorBanner message={error} /></div> : null}
      {status ? <div className="mt-4"><SuccessBanner message={status} /></div> : null}
      {forecast ? (
        <>
          <p className="mt-4 text-sm text-[var(--muted)]">
            Scenario <span className="font-medium text-[var(--foreground)]">{scenario}</span>
            {scenario === "conservative"
              ? " — income entries shown at 85% for planning stress."
              : scenario === "optimistic"
                ? " — income entries shown at 115%."
                : " — expected recurring and confirmed entries as recorded."}
          </p>
          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            <MetricTile label="Starting balance" value={forecast.starting_balance_gbp} />
            <MetricTile
              label="Projected balance"
              value={
                forecast.projected_balance_gbp +
                forecast.entries
                  .filter((entry) => entry.entry_type === "income")
                  .reduce((sum, entry) => {
                    const base = entry.amount_gbp;
                    const factor =
                      scenario === "conservative" ? 0.85 : scenario === "optimistic" ? 1.15 : 1;
                    return sum + base * (factor - 1);
                  }, 0)
              }
              warning={forecast.cash_pressure_warning}
            />
            <MetricTile label="Horizon" value={forecast.horizon_days} format="number" hint="days" />
          </div>
          {forecast.cash_pressure_warning ? (
            <p className="mt-4 rounded-xl border border-amber-400/35 bg-amber-500/10 px-4 py-3 text-sm">
              {forecast.warning_message}
            </p>
          ) : null}
          {forecast.columns.length > 1 ? (
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              {forecast.columns.map((column) => (
                <section key={column.scope} className="rounded-2xl border border-[var(--border)] p-4">
                  <h2 className="text-sm font-semibold">
                    {column.scope === "business" ? COMPANY_SHORT : PERSONAL_LEDGER}
                  </h2>
                  <p className="mt-2 text-sm text-[var(--muted)]">
                    Start {formatGbp(column.starting_balance_gbp)} · Projected{" "}
                    {formatGbp(column.projected_balance_gbp)}
                  </p>
                </section>
              ))}
            </div>
          ) : null}
          <ul className="mt-6 space-y-2">
            {forecast.entries.map((entry) => (
              <li
                key={entry.id}
                className="flex items-center justify-between gap-3 rounded-xl border border-[var(--border)] px-4 py-3 text-sm"
              >
                <span>
                  {entry.label}{" "}
                  <span className="text-[var(--muted)]">
                    · {entry.forecast_date} · {entry.entry_type} · {entry.scope}
                  </span>
                </span>
                <span className="flex items-center gap-3">
                  <span className={`font-semibold tabular-nums ${entry.amount_gbp >= 0 ? "text-emerald-600" : ""}`}>
                    {formatGbp(entry.amount_gbp)}
                  </span>
                  {canWrite(user) ? (
                    <button type="button" className="solar-btn-ghost text-xs" onClick={() => setDeleteId(entry.id)}>
                      Remove
                    </button>
                  ) : null}
                </span>
              </li>
            ))}
            {forecast.entries.length === 0 ? (
              <li className="text-sm text-[var(--muted)]">No forecast entries in this horizon.</li>
            ) : null}
          </ul>
        </>
      ) : (
        <p className="mt-8 text-sm text-[var(--muted)]">Loading forecast…</p>
      )}
      {canWrite(user) ? (
        <form
          onSubmit={(event) => void addEntry(event)}
          className="mt-6 grid gap-3 rounded-2xl border border-[var(--border)] p-4 sm:grid-cols-2 lg:grid-cols-6"
        >
          <input
            className="solar-input"
            placeholder="Label"
            value={form.label}
            onChange={(event) => setForm({ ...form, label: event.target.value })}
            required
          />
          <input
            className="solar-input"
            placeholder="Amount (+ in / − out)"
            value={form.amount_gbp}
            onChange={(event) => setForm({ ...form, amount_gbp: event.target.value })}
            required
          />
          <input
            className="solar-input"
            type="date"
            value={form.forecast_date}
            onChange={(event) => setForm({ ...form, forecast_date: event.target.value })}
            required
          />
          <select className="solar-input" value={form.entry_type} onChange={(event) => setForm({ ...form, entry_type: event.target.value })}>
            <option value="income">Income</option>
            <option value="bill">Bill</option>
            <option value="debt">Debt</option>
            <option value="tax_vat">Tax / VAT</option>
            <option value="other">Other</option>
          </select>
          <select className="solar-input" value={form.scope} onChange={(event) => setForm({ ...form, scope: event.target.value })}>
            <option value="personal">Personal</option>
            <option value="business">Business</option>
          </select>
          <button type="submit" className="solar-btn-primary" disabled={saving}>
            {saving ? "Saving…" : "Add entry"}
          </button>
        </form>
      ) : null}
      <ConfirmDialog
        open={deleteId != null}
        title="Remove this forecast entry?"
        description="This only changes the forecast. Live account and debt records stay as they are."
        confirmLabel="Remove"
        onCancel={() => setDeleteId(null)}
        onConfirm={() => void removeEntry()}
      />
    </AppShell>
  );
}
