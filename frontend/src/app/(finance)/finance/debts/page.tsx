"use client";

import { Fragment, useCallback, useMemo, useState } from "react";
import { z } from "zod";

import { BankImportCard } from "@/components/finance/BankImportCard";
import { DebtReductionPlanPanel } from "@/components/finance/DebtReductionPlanPanel";
import { FinanceDataGapsBanner } from "@/components/finance/FinanceDataGapsBanner";
import { SavedFiguresBanner } from "@/components/finance/SavedFiguresBanner";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner, SuccessBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { apiClient } from "@/lib/api-client";
import { useRequireAuth } from "@/lib/use-require-auth";
import {
  debtScenarioSchema,
  dualDebtStrategiesSchema,
  financeLiabilitySchema,
  type DebtStrategy,
  type DualDebtStrategies,
  type FinanceLiability,
} from "@/lib/finance-schemas";
import {
  debtGapLabels,
  displayOriginalBalanceGbp,
  groupDebts,
} from "@/lib/finance-debt-groups";
import { notifyFinanceChanged } from "@/lib/finance-events";
import { useFinanceBackgroundLiveRefresh } from "@/lib/use-finance-background-live-refresh";
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
  const { user, gated, redirecting } = useRequireAuth();
  const [debts, setDebts] = useState<FinanceLiability[]>([]);
  const [strategies, setStrategies] = useState<DualDebtStrategies | null>(null);
  const [planTab, setPlanTab] = useState<"personal" | "business">("personal");
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
  const [hydrated, setHydrated] = useState(false);

  const load = useCallback(async () => {
    try {
      const list = await apiClient.get<unknown>("/finance/liabilities");
      setDebts(z.array(financeLiabilitySchema).parse(list));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load debts");
    }
    try {
      const strat = await apiClient.get<unknown>("/finance/debts/strategy");
      setStrategies(dualDebtStrategiesSchema.parse(strat));
    } catch {
      setStrategies(null);
    } finally {
      setHydrated(true);
    }
  }, []);


  useFinanceReload(load, Boolean(user));
  const { refreshing } = useFinanceBackgroundLiveRefresh(user);

  const analysisById = useMemo(() => {
    const map = new Map<number, NonNullable<DebtStrategy["analysis"]>[number]>();
    for (const item of strategies?.personal.analysis ?? []) map.set(item.id, item);
    for (const item of strategies?.business.analysis ?? []) map.set(item.id, item);
    return map;
  }, [strategies]);

  const activePlan: DebtStrategy | null = strategies
    ? planTab === "personal"
      ? strategies.personal
      : strategies.business
    : null;

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
      original_balance_gbp: (() => {
        const original = displayOriginalBalanceGbp(debt);
        return original == null ? "" : String(original);
      })(),
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

  if (gated) return <AuthLoadingShell redirecting={redirecting} />;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Debts"
        description="Credit cards, loans, and Funding Circle. Log in to your bank to pull them in, or add one below."
      />
      {error ? <div className="mt-4"><ErrorBanner message={error} /></div> : null}
      {status ? <div className="mt-4"><SuccessBanner message={status} /></div> : null}
      <div className="mt-4">
        <SavedFiguresBanner refreshing={refreshing} />
      </div>
      <p className="mt-4 text-sm text-[var(--muted)]">
        Personal {formatGbp(personalTotal)} · Business {formatGbp(businessTotal)}
        {companyOwesDirector > 0 ? ` · Company owes Robert ${formatGbp(companyOwesDirector)}` : ""}
        {directorOwesCompany > 0 ? ` · Robert owes the company ${formatGbp(directorOwesCompany)}` : ""}
      </p>
      {directorsLoans.length > 0 ? (
        <p className="mt-3 rounded-xl border border-emerald-400/35 bg-emerald-500/10 px-4 py-3 text-sm">
          Director&apos;s loan is money between Robert and the company — never a lender to repay.
          It stays out of both debt reduction plans and combined external debt.
        </p>
      ) : null}

      <div className="mt-6">
        <FinanceDataGapsBanner
          extraLines={(() => {
            const lines: string[] = [];
            const unknown = repayableDebts.filter((d) => d.interest_rate_known === false);
            const missingLimits = repayableDebts.filter(
              (d) => debtUsesCreditLimit(d.debt_type) && (d.credit_limit_gbp == null || d.credit_limit_gbp <= 0),
            );
            if (unknown.length) {
              lines.push(
                `APR unknown: ${unknown.map((d) => d.name).slice(0, 4).join(", ")}${unknown.length > 4 ? "…" : ""}.`,
              );
            }
            if (missingLimits.length) {
              lines.push(
                `Credit limit missing: ${missingLimits.map((d) => d.name).slice(0, 4).join(", ")}${missingLimits.length > 4 ? "…" : ""}.`,
              );
            }
            if (strategies?.personal.incomplete) {
              lines.push(`Personal plan incomplete: ${strategies.personal.incomplete_reason}`);
            }
            if (strategies?.business.incomplete) {
              lines.push(`Business plan incomplete: ${strategies.business.incomplete_reason}`);
            }
            return lines;
          })()}
        />
      </div>

      <section className="mt-8" aria-label="Debt reduction plans">
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Debt plan scope">
          {(["personal", "business"] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              role="tab"
              aria-selected={planTab === tab}
              onClick={() => setPlanTab(tab)}
              className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${
                planTab === tab
                  ? "bg-emerald-600 text-white"
                  : "border border-[var(--border)] text-[var(--muted)]"
              }`}
            >
              {tab} plan
            </button>
          ))}
        </div>
        <div className="mt-4 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
          <DebtReductionPlanPanel plan={activePlan} loading={!hydrated} />
          {canWrite(user) ? (
            <form
              className="mt-4 flex flex-wrap gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                const extra = optionalMoney(customExtra);
                if (extra == null) return;
                void (async () => {
                  try {
                    const data = await apiClient.get<unknown>(
                      `/finance/debts/scenarios?extra=${extra}&scope=${planTab}`,
                    );
                    const parsed = z.array(debtScenarioSchema).parse(data);
                    setStrategies((current) => {
                      if (!current) return current;
                      return {
                        ...current,
                        [planTab]: { ...current[planTab], scenarios: parsed },
                      };
                    });
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
                Model custom extra on {planTab}
              </button>
            </form>
          ) : null}
        </div>
      </section>

      {!hydrated ? (
        <p className="mt-6 text-sm text-[var(--muted)]">Loading debts…</p>
      ) : repayableDebts.length === 0 ? (
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
              <th className="py-2 pr-3">Balance</th>
              <th className="py-2 pr-3">APR</th>
              <th className="py-2 pr-3">Min payment</th>
              <th className="py-2 pr-3">Interest / mo</th>
              <th className="py-2 pr-3">Priority</th>
              <th className="py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {groupDebts(visible).map((group) => (
              <Fragment key={group.key}>
                <tr className="bg-[var(--surface)]">
                  <td colSpan={7} className="py-3 pr-3 pt-5 text-xs font-bold uppercase tracking-[0.14em] text-[var(--muted)]">
                    {group.title}
                  </td>
                </tr>
                {group.debts.map((debt) => {
                  const info = analysisById.get(debt.id);
                  const gaps = debtGapLabels(debt);
                  const interestIncomplete = debt.interest_rate_known === false;
                  return (
                    <tr key={debt.id} className="border-b border-[var(--border)] align-top">
                      <td className="py-3 pr-3">
                        {debt.name}
                        {debt.debt_type === "mortgage" ? (
                          <span className="block text-xs text-[var(--muted)]">
                            Confirmed half-share of £164,421 joint mortgage
                          </span>
                        ) : null}
                        {debtUsesCreditLimit(debt.debt_type) ? (
                          <span className="block text-xs text-[var(--muted)]">
                            {debt.credit_limit_gbp
                              ? `Limit ${formatGbp(debt.credit_limit_gbp)}`
                              : "Credit limit missing"}
                          </span>
                        ) : null}
                        {gaps.length > 0 ? (
                          <span className="mt-1 block text-xs font-medium text-amber-800 dark:text-amber-200">
                            {gaps.join(" · ")}
                          </span>
                        ) : null}
                      </td>
                      <td className="py-3 pr-3 tabular-nums">{formatGbp(debt.balance_gbp)}</td>
                      <td className="py-3 pr-3">
                        {debt.interest_rate_known === false ? "APR unknown" : formatPercent(debt.interest_rate_pct)}
                      </td>
                      <td className="py-3 pr-3 tabular-nums">{formatGbp(debt.minimum_payment_gbp)}</td>
                      <td className="py-3 pr-3 tabular-nums">
                        {interestIncomplete
                          ? "Incomplete"
                          : info?.monthly_interest_gbp == null
                            ? "—"
                            : formatGbp(info.monthly_interest_gbp)}
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
              </Fragment>
            ))}
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
            placeholder="Original balance (not the old £175k placeholder)"
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
