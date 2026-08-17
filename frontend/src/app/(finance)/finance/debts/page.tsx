"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { z } from "zod";

import { BankImportCard } from "@/components/finance/BankImportCard";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner, SuccessBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import {
  debtScenarioSchema,
  debtStrategySchema,
  financeLiabilitySchema,
  type DebtStrategy,
  type FinanceLiability,
} from "@/lib/finance-schemas";
import { notifyFinanceChanged } from "@/lib/finance-events";
import { useFinanceReload } from "@/lib/use-finance-reload";
import { debtUsesCreditLimit, optionalMoney, requiredMoney } from "@/lib/finance-form";
import { formatGbp, formatPercent } from "@/lib/money";
import { canWrite } from "@/lib/permissions";

type SortKey = "apr" | "balance" | "interest" | "payment" | "priority";

const emptyForm = {
  name: "",
  scope: "personal",
  debt_type: "credit_card",
  balance_gbp: "",
  interest_rate_pct: "",
  minimum_payment_gbp: "",
  overpayment_gbp: "",
  original_balance_gbp: "",
  payment_day: "",
  credit_limit_gbp: "",
  dla_direction: "company_owes_director",
};

export default function DebtsPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [debts, setDebts] = useState<FinanceLiability[]>([]);
  const [strategy, setStrategy] = useState<DebtStrategy | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [scopeFilter, setScopeFilter] = useState<"all" | "personal" | "business">("all");
  const [aprFilter, setAprFilter] = useState<"all" | "high">("all");
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("priority");
  const [customExtra, setCustomExtra] = useState("100");
  const [archiveId, setArchiveId] = useState<number | null>(null);

  const load = useCallback(async () => {
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
    }
  }, []);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useFinanceReload(load, Boolean(user));

  const analysisById = useMemo(() => {
    const map = new Map<number, NonNullable<DebtStrategy["analysis"]>[number]>();
    for (const item of strategy?.analysis ?? []) map.set(item.id, item);
    return map;
  }, [strategy]);

  const repayableDebts = useMemo(
    () => debts.filter((debt) => debt.debt_type !== "directors_loan"),
    [debts],
  );
  const directorsLoans = useMemo(
    () => debts.filter((debt) => debt.debt_type === "directors_loan"),
    [debts],
  );

  const visible = useMemo(() => {
    const query = search.trim().toLowerCase();
    const filtered = repayableDebts.filter((debt) => {
      if (scopeFilter !== "all" && debt.scope !== scopeFilter) return false;
      if (aprFilter === "high" && debt.interest_rate_pct < 12) return false;
      if (query && !debt.name.toLowerCase().includes(query)) return false;
      return true;
    });
    const sorted = [...filtered];
    sorted.sort((a, b) => {
      const aInfo = analysisById.get(a.id);
      const bInfo = analysisById.get(b.id);
      if (sortKey === "apr") return b.interest_rate_pct - a.interest_rate_pct;
      if (sortKey === "balance") return b.balance_gbp - a.balance_gbp;
      if (sortKey === "interest") return (bInfo?.monthly_interest_gbp ?? 0) - (aInfo?.monthly_interest_gbp ?? 0);
      if (sortKey === "payment") return b.minimum_payment_gbp - a.minimum_payment_gbp;
      return (bInfo?.priority_score ?? 0) - (aInfo?.priority_score ?? 0);
    });
    return sorted;
  }, [repayableDebts, scopeFilter, aprFilter, search, sortKey, analysisById]);

  const personalTotal = repayableDebts.filter((d) => d.scope === "personal").reduce((s, d) => s + d.balance_gbp, 0);
  const businessTotal = repayableDebts.filter((d) => d.scope === "business").reduce((s, d) => s + d.balance_gbp, 0);
  const companyOwesDirector = directorsLoans
    .filter((debt) => debt.dla_direction !== "director_owes_company")
    .reduce((sum, debt) => sum + debt.balance_gbp, 0);
  const directorOwesCompany = directorsLoans
    .filter((debt) => debt.dla_direction === "director_owes_company")
    .reduce((sum, debt) => sum + debt.balance_gbp, 0);

  function startEdit(debt: FinanceLiability) {
    setEditingId(debt.id);
    setForm({
      name: debt.name,
      scope: debt.scope,
      debt_type: debt.debt_type,
      balance_gbp: String(debt.balance_gbp),
      interest_rate_pct: debt.interest_rate_known === false ? "" : String(debt.interest_rate_pct),
      minimum_payment_gbp: String(debt.minimum_payment_gbp),
      overpayment_gbp: String(debt.overpayment_gbp),
      original_balance_gbp: debt.original_balance_gbp == null ? "" : String(debt.original_balance_gbp),
      payment_day: debt.payment_day == null ? "" : String(debt.payment_day),
      credit_limit_gbp: debt.credit_limit_gbp == null ? "" : String(debt.credit_limit_gbp),
      dla_direction: debt.dla_direction ?? "company_owes_director",
    });
  }

  async function saveDebt(event: React.FormEvent) {
    event.preventDefault();
    if (!canWrite(user) || saving) return;
    setSaving(true);
    setError(null);
    try {
      const apr = optionalMoney(form.interest_rate_pct);
      const payload = {
        scope: form.scope,
        name: form.name.trim(),
        debt_type: form.debt_type,
        balance_gbp: requiredMoney(form.balance_gbp, "balance"),
        interest_rate_pct: apr ?? 0,
        interest_rate_known: apr != null,
        minimum_payment_gbp: requiredMoney(form.minimum_payment_gbp, "minimum payment"),
        overpayment_gbp: optionalMoney(form.overpayment_gbp) ?? 0,
        original_balance_gbp: form.original_balance_gbp.trim()
          ? requiredMoney(form.original_balance_gbp, "original balance")
          : null,
        payment_day: form.payment_day.trim() ? Number(form.payment_day) : null,
        credit_limit_gbp:
          debtUsesCreditLimit(form.debt_type) && form.credit_limit_gbp.trim()
            ? requiredMoney(form.credit_limit_gbp, "credit limit")
            : null,
        dla_direction: form.debt_type === "directors_loan" ? form.dla_direction : null,
      };
      if (editingId) {
        await apiClient.put(`/finance/liabilities/${editingId}`, payload);
        setStatus("Debt updated");
      } else {
        await apiClient.post("/finance/liabilities", payload);
        setStatus("Debt added");
      }
      setForm(emptyForm);
      setEditingId(null);
      await load();
      notifyFinanceChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save debt");
    } finally {
      setSaving(false);
    }
  }

  async function archiveDebt() {
    if (archiveId == null) return;
    try {
      await apiClient.delete(`/finance/liabilities/${archiveId}`);
      setStatus("Debt archived");
      setArchiveId(null);
      await load();
      notifyFinanceChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to archive debt");
    }
  }

  if (authLoading || !user) return <AuthLoadingShell />;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Debts"
        description="Credit cards, loans, and Funding Circle. Log in to your bank to pull them in, or add one below."
      />
      {error ? <div className="mt-4"><ErrorBanner message={error} /></div> : null}
      {status ? <div className="mt-4"><SuccessBanner message={status} /></div> : null}
      <p className="mt-4 text-sm text-[var(--muted)]">
        Personal {formatGbp(personalTotal)} · Business {formatGbp(businessTotal)}
        {companyOwesDirector > 0 ? ` · Company owes you ${formatGbp(companyOwesDirector)}` : ""}
        {directorOwesCompany > 0 ? ` · You owe the company ${formatGbp(directorOwesCompany)}` : ""}
      </p>
      {directorsLoans.length > 0 ? (
        <p className="mt-3 rounded-xl border border-emerald-400/35 bg-emerald-500/10 px-4 py-3 text-sm">
          Director&apos;s loan is money the company owes you. It is kept out of payoff
          priority and household net worth so it is not treated as a debt you repay.
        </p>
      ) : null}
      {strategy && strategy.strategy !== "none" ? (
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

      {repayableDebts.length === 0 ? (
        <div className="mt-6 space-y-4">
          <div className="rounded-2xl border border-[var(--border)] px-4 py-3">
            <p className="font-medium">No debts recorded yet</p>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Credit cards and loans from a bank login appear here. You can also add
              one below. Funding Circle is pulled from the same bank feed.
            </p>
          </div>
          <BankImportCard readOnly={!canWrite(user)} showSettingsLink />
        </div>
      ) : null}

      {strategy?.scenarios?.length ? (
        <section className="mt-6">
          <h2 className="solar-section-title">What if I paid extra?</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Forecast only — extra amounts are not written to the debt until you edit it.
          </p>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-[var(--muted)]">
                  <th className="py-2 pr-3">Extra / month</th>
                  <th className="py-2 pr-3">Months saved</th>
                  <th className="py-2 pr-3">Interest saved</th>
                  <th className="py-2">Payoff</th>
                </tr>
              </thead>
              <tbody>
                {strategy.scenarios.map((row) => (
                  <tr key={row.extra_gbp} className="border-b border-[var(--border)]">
                    <td className="py-2 pr-3 tabular-nums">{formatGbp(row.extra_gbp)}</td>
                    <td className="py-2 pr-3">{row.incomplete ? row.reason : `${row.months_saved ?? "—"} mo`}</td>
                    <td className="py-2 pr-3 tabular-nums">{row.interest_saved_gbp == null ? "—" : formatGbp(row.interest_saved_gbp)}</td>
                    <td className="py-2">{row.payoff_date ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {canWrite(user) ? (
            <form
              className="mt-3 flex flex-wrap gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                const extra = optionalMoney(customExtra);
                if (extra == null) return;
                void (async () => {
                  try {
                    const data = await apiClient.get<unknown>(`/finance/debts/scenarios?extra=${extra}`);
                    const parsed = z.array(debtScenarioSchema).parse(data);
                    setStrategy((current) => (current ? { ...current, scenarios: parsed } : current));
                  } catch (err) {
                    setError(err instanceof Error ? err.message : "Failed to model scenario");
                  }
                })();
              }}
            >
              <input
                className="solar-input w-32"
                value={customExtra}
                onChange={(event) => setCustomExtra(event.target.value)}
                aria-label="Custom overpayment"
              />
              <button type="submit" className="solar-btn-ghost">
                Model custom extra
              </button>
            </form>
          ) : null}
        </section>
      ) : null}

      {repayableDebts.length > 0 ? (
      <>
      <div className="mt-6 flex flex-wrap gap-2">
        <input
          className="solar-input"
          placeholder="Search debts"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <select className="solar-input" value={scopeFilter} onChange={(event) => setScopeFilter(event.target.value as typeof scopeFilter)}>
          <option value="all">All scopes</option>
          <option value="personal">Personal</option>
          <option value="business">Business</option>
        </select>
        <select className="solar-input" value={aprFilter} onChange={(event) => setAprFilter(event.target.value as typeof aprFilter)}>
          <option value="all">All APRs</option>
          <option value="high">High APR (12%+)</option>
        </select>
        <select className="solar-input" value={sortKey} onChange={(event) => setSortKey(event.target.value as SortKey)}>
          <option value="priority">Recommended priority</option>
          <option value="apr">APR</option>
          <option value="balance">Balance</option>
          <option value="interest">Monthly interest</option>
          <option value="payment">Payment</option>
        </select>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[800px] text-left text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] text-[var(--muted)]">
              <th className="py-2 pr-3">Name</th>
              <th className="py-2 pr-3">Scope</th>
              <th className="py-2 pr-3">Balance</th>
              <th className="py-2 pr-3">APR</th>
              <th className="py-2 pr-3">Min payment</th>
              <th className="py-2 pr-3">Interest / mo</th>
              <th className="py-2 pr-3">Priority</th>
              <th className="py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((debt) => {
              const info = analysisById.get(debt.id);
              return (
                <tr key={debt.id} className="border-b border-[var(--border)]">
                  <td className="py-3 pr-3">
                    {debt.name}
                    {debtUsesCreditLimit(debt.debt_type) && debt.credit_limit_gbp ? (
                      <span className="block text-xs text-[var(--muted)]">
                        Limit {formatGbp(debt.credit_limit_gbp)}
                      </span>
                    ) : null}
                  </td>
                  <td className="py-3 pr-3 capitalize">{debt.scope}</td>
                  <td className="py-3 pr-3 tabular-nums">{formatGbp(debt.balance_gbp)}</td>
                  <td className="py-3 pr-3">
                    {debt.interest_rate_known === false ? "Unknown" : formatPercent(debt.interest_rate_pct)}
                  </td>
                  <td className="py-3 pr-3 tabular-nums">{formatGbp(debt.minimum_payment_gbp)}</td>
                  <td className="py-3 pr-3 tabular-nums">
                    {info?.monthly_interest_gbp == null ? "—" : formatGbp(info.monthly_interest_gbp)}
                  </td>
                  <td className="py-3 pr-3">{info?.priority_label ?? "—"}</td>
                  <td className="py-3">
                    {canWrite(user) ? (
                      <div className="flex flex-wrap gap-2">
                        <button type="button" className="solar-btn-ghost text-xs" onClick={() => startEdit(debt)}>
                          Edit
                        </button>
                        <button type="button" className="solar-btn-ghost text-xs" onClick={() => setArchiveId(debt.id)}>
                          Archive
                        </button>
                      </div>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {visible.length === 0 ? (
          <p className="mt-4 text-sm text-[var(--muted)]">No debts match the current filters.</p>
        ) : null}
      </div>
      </>
      ) : null}

      {canWrite(user) ? (
        <form
          onSubmit={(event) => void saveDebt(event)}
          className="mt-6 grid gap-3 rounded-2xl border border-[var(--border)] p-4 md:grid-cols-3 lg:grid-cols-4"
        >
          <h2 className="solar-section-title md:col-span-3 lg:col-span-4">
            {editingId ? "Edit debt" : "Add debt"}
          </h2>
          <input
            className="solar-input"
            placeholder="Name"
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
            required
          />
          <select
            className="solar-input"
            aria-label="Debt scope"
            value={form.scope}
            onChange={(event) => setForm({ ...form, scope: event.target.value })}
          >
            <option value="personal">Personal</option>
            <option value="business">Business</option>
          </select>
          <select className="solar-input" value={form.debt_type} onChange={(event) => setForm({ ...form, debt_type: event.target.value })}>
            <option value="credit_card">Credit card</option>
            <option value="loan">Loan</option>
            <option value="mortgage">Mortgage</option>
            <option value="business_loan">Business loan</option>
            <option value="directors_loan">Director&apos;s loan</option>
            <option value="other">Other</option>
          </select>
          <input
            className="solar-input"
            placeholder="Balance"
            value={form.balance_gbp}
            onChange={(event) => setForm({ ...form, balance_gbp: event.target.value })}
            required
          />
          <input
            className="solar-input"
            placeholder="APR % (optional)"
            value={form.interest_rate_pct}
            onChange={(event) => setForm({ ...form, interest_rate_pct: event.target.value })}
          />
          {debtUsesCreditLimit(form.debt_type) ? (
            <input
              className="solar-input"
              placeholder="Credit limit"
              value={form.credit_limit_gbp}
              onChange={(event) => setForm({ ...form, credit_limit_gbp: event.target.value })}
            />
          ) : null}
          {form.debt_type === "directors_loan" ? (
            <select
              className="solar-input"
              aria-label="Director's loan direction"
              value={form.dla_direction}
              onChange={(event) => setForm({ ...form, dla_direction: event.target.value })}
            >
              <option value="director_owes_company">Robert owes the company</option>
              <option value="company_owes_director">Company owes Robert</option>
            </select>
          ) : null}
          <input
            className="solar-input"
            placeholder="Minimum payment"
            value={form.minimum_payment_gbp}
            onChange={(event) => setForm({ ...form, minimum_payment_gbp: event.target.value })}
            required
          />
          <input
            className="solar-input"
            placeholder="Overpayment"
            value={form.overpayment_gbp}
            onChange={(event) => setForm({ ...form, overpayment_gbp: event.target.value })}
          />
          <input
            className="solar-input"
            placeholder="Original balance"
            value={form.original_balance_gbp}
            onChange={(event) => setForm({ ...form, original_balance_gbp: event.target.value })}
          />
          <input
            className="solar-input"
            placeholder="Payment day (1-31)"
            value={form.payment_day}
            onChange={(event) => setForm({ ...form, payment_day: event.target.value })}
          />
          <div className="flex gap-2">
            <button type="submit" className="solar-btn-primary" disabled={saving}>
              {saving ? "Saving…" : editingId ? "Update debt" : "Add debt"}
            </button>
            {editingId ? (
              <button
                type="button"
                className="solar-btn-ghost"
                onClick={() => {
                  setEditingId(null);
                  setForm(emptyForm);
                }}
              >
                Cancel
              </button>
            ) : null}
          </div>
        </form>
      ) : null}

      <ConfirmDialog
        open={archiveId != null}
        title="Archive this debt?"
        description="It will drop out of active totals. You can add it again later if needed."
        confirmLabel="Archive"
        onCancel={() => setArchiveId(null)}
        onConfirm={() => void archiveDebt()}
      />
    </AppShell>
  );
}
