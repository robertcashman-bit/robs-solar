"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { summariseBudgetLines } from "@/lib/budget-totals";
import { COMPANY_SHORT, PERSONAL_LEDGER } from "@/lib/finance-branding";
import { budgetPlanSchema, type BudgetPlan, type BudgetPlanLine } from "@/lib/finance-schemas";
import { formatGbp } from "@/lib/money";

type ScopeKey = "personal" | "business";

type ScopeSection = {
  scope: ScopeKey;
  title: string;
  plan: BudgetPlan | null;
  lines: BudgetPlanLine[];
  incomeGbp: number;
  spendingGbp: number;
  surplusGbp: number;
};

function scopeLines(plan: BudgetPlan | null, scope: ScopeKey): BudgetPlanLine[] {
  if (!plan) return [];
  return plan.lines.filter((line) => line.scope === scope);
}

function sectionFor(
  scope: ScopeKey,
  title: string,
  plan: BudgetPlan | null,
  incomeGbp: number,
): ScopeSection {
  const lines = scopeLines(plan, scope);
  const totals = summariseBudgetLines(lines, incomeGbp);
  return {
    scope,
    title,
    plan,
    lines,
    incomeGbp: totals.income_gbp,
    spendingGbp: totals.total_spending_gbp,
    surplusGbp: totals.surplus_gbp,
  };
}

function ScopeBudgetSection({ section }: { section: ScopeSection }) {
  const scopeWord = section.scope === "business" ? "Business" : "Personal";
  const surplusLabel =
    section.surplusGbp < 0
      ? `Shortfall ${formatGbp(Math.abs(section.surplusGbp))}`
      : `Surplus ${formatGbp(section.surplusGbp)}`;
  const surplusClass =
    section.surplusGbp < 0
      ? "text-red-600 dark:text-red-400"
      : "text-emerald-600 dark:text-emerald-400";

  return (
    <section
      aria-label={`${section.title} active budget`}
      className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5"
    >
      <div>
        <p className="text-[0.65rem] font-bold uppercase tracking-[0.14em] text-[var(--muted)]">
          {section.scope === "business" ? "Business / company" : "Personal"}
        </p>
        <h3 className="mt-1 text-lg font-semibold">{section.title} budget</h3>
        {section.plan ? (
          <p className="mt-0.5 text-sm text-[var(--muted)]">
            {section.plan.name} · {section.plan.style.replaceAll("_", " ")}. A plan, not actual
            cashflow.
          </p>
        ) : (
          <p className="mt-0.5 text-sm text-[var(--muted)]">No active {section.scope} plan yet.</p>
        )}
      </div>

      {section.plan ? (
        <>
          <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-sunken)]/40 px-3 py-2">
              <dt className="text-xs uppercase tracking-wide text-[var(--muted)]">
                {scopeWord} income
              </dt>
              <dd className="mt-1 text-lg font-semibold tabular-nums">
                {formatGbp(section.incomeGbp)}
              </dd>
            </div>
            <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-sunken)]/40 px-3 py-2">
              <dt className="text-xs uppercase tracking-wide text-[var(--muted)]">
                {scopeWord} spending
              </dt>
              <dd className="mt-1 text-lg font-semibold tabular-nums">
                {formatGbp(section.spendingGbp)}
              </dd>
            </div>
            <div className="col-span-2 rounded-xl border border-[var(--border)] bg-[var(--surface-sunken)]/40 px-3 py-2 sm:col-span-1">
              <dt className="text-xs uppercase tracking-wide text-[var(--muted)]">
                {scopeWord} surplus / shortfall
              </dt>
              <dd className={`mt-1 text-sm font-semibold ${surplusClass}`}>{surplusLabel}</dd>
            </div>
          </dl>

          {section.lines.length > 0 ? (
            <ul className="mt-4 divide-y divide-[var(--border)] border-t border-[var(--border)]">
              {section.lines.map((line) => (
                <li
                  key={`${section.scope}-${line.category}-${line.id ?? line.sort_order}`}
                  className="flex items-center justify-between gap-3 py-2 text-sm"
                >
                  <span>
                    <span className="font-medium">{line.category}</span>
                    <span className="ml-2 text-xs text-[var(--muted)]">{scopeWord}</span>
                  </span>
                  <span className="font-semibold tabular-nums">{formatGbp(line.amount_gbp)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-4 text-sm text-[var(--muted)]">
              Active plan has no {section.scope} lines yet.
            </p>
          )}
        </>
      ) : null}
    </section>
  );
}

type ActiveBudgetsBreakdownProps = {
  personalPlan?: BudgetPlan | null;
  businessPlan?: BudgetPlan | null;
  fetchPlans?: boolean;
  showOpenLink?: boolean;
};

export function ActiveBudgetsBreakdown({
  personalPlan: personalProp,
  businessPlan: businessProp,
  fetchPlans = true,
  showOpenLink = true,
}: ActiveBudgetsBreakdownProps) {
  const [personalPlan, setPersonalPlan] = useState<BudgetPlan | null>(personalProp ?? null);
  const [businessPlan, setBusinessPlan] = useState<BudgetPlan | null>(businessProp ?? null);
  const [loading, setLoading] = useState(fetchPlans);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!fetchPlans) return;
    setLoading(true);
    try {
      const [personalRaw, businessRaw] = await Promise.all([
        apiClient.get<unknown>("/finance/budgets/active?scope=personal"),
        apiClient.get<unknown>("/finance/budgets/active?scope=business"),
      ]);
      setPersonalPlan(personalRaw == null ? null : budgetPlanSchema.parse(personalRaw));
      setBusinessPlan(businessRaw == null ? null : budgetPlanSchema.parse(businessRaw));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load active budgets");
    } finally {
      setLoading(false);
    }
  }, [fetchPlans]);

  useEffect(() => {
    if (!fetchPlans) {
      setPersonalPlan(personalProp ?? null);
      setBusinessPlan(businessProp ?? null);
      setLoading(false);
      return;
    }
    const timer = window.setTimeout(() => void load(), 0);
    const onChanged = () => {
      void load();
    };
    window.addEventListener("robs-finance-changed", onChanged);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("robs-finance-changed", onChanged);
    };
  }, [fetchPlans, load, personalProp, businessProp]);

  const samePlan =
    personalPlan != null && businessPlan != null && personalPlan.id === businessPlan.id;

  let personalIncome = personalPlan?.income_gbp ?? 0;
  let businessIncome = businessPlan?.income_gbp ?? 0;
  if (samePlan) {
    // Combined plans carry a single income_gbp for all lines. Split that income
    // by scoped spending so each column's surplus is consistent and the two
    // surpluses sum to income − all lines (the plan's real surplus).
    const personalSpend = scopeLines(personalPlan, "personal").reduce(
      (sum, line) => sum + (Number(line.amount_gbp) || 0),
      0,
    );
    const businessSpend = scopeLines(businessPlan, "business").reduce(
      (sum, line) => sum + (Number(line.amount_gbp) || 0),
      0,
    );
    const totalSpend = personalSpend + businessSpend;
    const income = personalPlan!.income_gbp;
    if (totalSpend <= 0) {
      personalIncome = income;
      businessIncome = 0;
    } else {
      personalIncome = Math.round(((income * personalSpend) / totalSpend) * 100) / 100;
      businessIncome = Math.round((income - personalIncome) * 100) / 100;
    }
  } else {
    if (personalPlan?.active_scope === "business") personalIncome = 0;
    if (businessPlan?.active_scope === "personal") businessIncome = 0;
  }

  const personalSection = sectionFor("personal", PERSONAL_LEDGER, personalPlan, personalIncome);
  const businessSection = sectionFor("business", COMPANY_SHORT, businessPlan, businessIncome);

  return (
    <div className="space-y-4" aria-label="Active budgets by scope">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Active budgets</h2>
          <p className="mt-0.5 text-sm text-[var(--muted)]">
            Personal and business plans listed separately with every category line.
          </p>
        </div>
        {showOpenLink ? (
          <Link href="/finance/budget" className="solar-btn-secondary text-sm">
            Open Budget
          </Link>
        ) : null}
      </div>
      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}
      {loading ? (
        <p className="text-sm text-[var(--muted)]">Loading active budgets…</p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <ScopeBudgetSection section={personalSection} />
          <ScopeBudgetSection section={businessSection} />
        </div>
      )}
    </div>
  );
}
