"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { z } from "zod";

import { FinanceAmount } from "@/components/finance/FinanceAmount";
import { AppShell } from "@/components/shared/AppShell";
import { HistoricBadge } from "@/components/finance/HistoricBadge";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { EmptyState } from "@/components/shared/EmptyState";
import { PageHeader } from "@/components/shared/PageHeader";
import { PageLoading } from "@/components/shared/PageLoading";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import {
  debtStrategySchema,
  financeLiabilitySchema,
  type DebtStrategy,
  type FinanceLiability,
} from "@/lib/finance-schemas";
import { formatPercent, financeRoleForDebtType } from "@/lib/money";
import { canWrite } from "@/lib/permissions";

export default function DebtsPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [debts, setDebts] = useState<FinanceLiability[]>([]);
  const [strategy, setStrategy] = useState<DebtStrategy | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    name: "",
    scope: "personal",
    debt_type: "credit_card",
    balance_gbp: "",
    interest_rate_pct: "",
    minimum_payment_gbp: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [list, strat] = await Promise.all([
        apiClient.get<unknown>("/finance/liabilities"),
        apiClient.get<unknown>("/finance/debts/strategy"),
      ]);
      setDebts(z.array(financeLiabilitySchema).parse(list));
      setStrategy(debtStrategySchema.parse(strat));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load debts");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [user, load]);

  async function addDebt(e: React.FormEvent) {
    e.preventDefault();
    if (!canWrite(user)) return;
    setSaving(true);
    setError(null);
    try {
      await apiClient.post("/finance/liabilities", {
        scope: form.scope,
        name: form.name,
        debt_type: form.debt_type,
        balance_gbp: Number(form.balance_gbp),
        interest_rate_pct: Number(form.interest_rate_pct),
        minimum_payment_gbp: Number(form.minimum_payment_gbp),
      });
      setForm({
        name: "",
        scope: "personal",
        debt_type: "credit_card",
        balance_gbp: "",
        interest_rate_pct: "",
        minimum_payment_gbp: "",
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add debt");
    } finally {
      setSaving(false);
    }
  }

  if (authLoading || !user) return <AuthLoadingShell />;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Debts"
        description="All liabilities with payoff strategy, interest rates, and debt-free estimates."
      />
      {error ? (
        <div className="mt-4">
          <ErrorBanner message={error} />
        </div>
      ) : null}
      {loading ? (
        <div className="mt-6">
          <PageLoading label="Loading debts" rows={2} />
        </div>
      ) : (
        <>
          {strategy ? (
            <div className="mt-6 rounded-2xl border border-emerald-400/35 bg-emerald-500/10 p-4">
              <p className="font-semibold">{strategy.headline}</p>
              <p className="mt-1 text-sm">{strategy.message}</p>
              {strategy.estimated_debt_free_date ? (
                <p className="mt-2 text-xs text-[var(--muted)]">
                  Target debt-free: {strategy.estimated_debt_free_date}
                </p>
              ) : null}
            </div>
          ) : null}
          {debts.length === 0 ? (
            <div className="mt-6">
              <EmptyState
                title="No debts recorded yet"
                description="Add credit cards, loans, or mortgages to track balances, rates, and payoff strategy."
              />
            </div>
          ) : (
            <div className="mt-6 overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] text-[var(--muted)]">
                    <th className="py-2 pr-4">Name</th>
                    <th className="py-2 pr-4">Scope</th>
                    <th className="py-2 pr-4">Balance</th>
                    <th className="py-2 pr-4">Rate</th>
                    <th className="py-2 pr-4">Min payment</th>
                    <th className="py-2">Overpayment</th>
                  </tr>
                </thead>
                <tbody>
                  {debts.map((d) => (
                    <tr key={d.id} className="border-b border-[var(--border)]">
                      <td className="py-3 pr-4">
                        {d.name}
                        {d.is_historic ? <HistoricBadge /> : null}
                      </td>
                      <td className="py-3 pr-4 capitalize">{d.scope}</td>
                      <td className="py-3 pr-4">
                        <FinanceAmount value={d.balance_gbp} role={financeRoleForDebtType(d.debt_type)} />
                      </td>
                      <td className="py-3 pr-4">{formatPercent(d.interest_rate_pct)}</td>
                      <td className="py-3 pr-4">
                        <FinanceAmount value={d.minimum_payment_gbp} role="outflow" />
                      </td>
                      <td className="py-3">
                        <FinanceAmount value={d.overpayment_gbp} role="outflow" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {canWrite(user) ? (
            <form
              onSubmit={(e) => void addDebt(e)}
              className="mt-6 grid gap-3 rounded-2xl border border-[var(--border)] p-4 md:grid-cols-3 lg:grid-cols-6"
            >
              <input
                className="solar-input"
                placeholder="Name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
              <select
                className="solar-input"
                value={form.scope}
                onChange={(e) => setForm({ ...form, scope: e.target.value })}
              >
                <option value="personal">Personal</option>
                <option value="business">Business</option>
              </select>
              <select
                className="solar-input"
                value={form.debt_type}
                onChange={(e) => setForm({ ...form, debt_type: e.target.value })}
              >
                <option value="credit_card">Credit card</option>
                <option value="loan">Loan</option>
                <option value="mortgage">Mortgage</option>
                <option value="business_loan">Business loan</option>
                <option value="directors_loan">Director&apos;s loan</option>
              </select>
              <input
                className="solar-input"
                type="number"
                placeholder="Balance"
                value={form.balance_gbp}
                onChange={(e) => setForm({ ...form, balance_gbp: e.target.value })}
                required
              />
              <input
                className="solar-input"
                type="number"
                step="0.01"
                placeholder="Rate %"
                value={form.interest_rate_pct}
                onChange={(e) => setForm({ ...form, interest_rate_pct: e.target.value })}
                required
              />
              <button type="submit" className="solar-btn-primary" disabled={saving}>
                {saving ? "Saving…" : "Add debt"}
              </button>
            </form>
          ) : null}
        </>
      )}
    </AppShell>
  );
}
