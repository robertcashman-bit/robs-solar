"use client";

import { useCallback, useState } from "react";
import { z } from "zod";

import { AccountManager } from "@/components/finance/AccountManager";
import { CashflowPlanPanel } from "@/components/finance/CashflowPlanPanel";
import { DebtReductionPlanPanel } from "@/components/finance/DebtReductionPlanPanel";
import { DebtStackPanel } from "@/components/finance/DebtStackPanel";
import { FinanceDataGapsBanner } from "@/components/finance/FinanceDataGapsBanner";
import { FinancePeriodScopeControl } from "@/components/finance/FinancePeriodScopeControl";
import { MetricTile } from "@/components/finance/MetricTile";
import { PlComparePanel } from "@/components/finance/PlComparePanel";
import { SavedFiguresBanner } from "@/components/finance/SavedFiguresBanner";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner, SuccessBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { apiClient } from "@/lib/api-client";
import { useRequireAuth } from "@/lib/use-require-auth";
import {
  budgetPlanSchema,
  debtStrategySchema,
  dualCashflowPlansSchema,
  financeOverviewSchema,
  parseFinanceAccounts,
  parseFinanceLiabilities,
  periodFlowSummarySchema,
  personalFinanceSnapshotSchema,
  type BudgetPlan,
  type DebtStrategy,
  type FinanceAccount,
  type FinanceLiability,
  type FinanceOverview,
  type PeriodFlowSummary,
  type PersonalFinanceSnapshot,
  type ScopedCashflowPlan,
} from "@/lib/finance-schemas";
import { useFinanceBackgroundLiveRefresh } from "@/lib/use-finance-background-live-refresh";
import { useFinancePeriod } from "@/lib/use-finance-period";
import { useFinanceReload } from "@/lib/use-finance-reload";
import { currentMonthKey, formatGbp, isCurrentMonthSnapshot, parseGbp } from "@/lib/money";
import { notifyFinanceChanged } from "@/lib/finance-events";
import { canWrite } from "@/lib/permissions";

const ACCOUNT_OPTIONS = [
  { value: "current", label: "Current" },
  { value: "credit_card", label: "Credit card" },
  { value: "loan", label: "Loan" },
  { value: "mortgage", label: "Mortgage" },
  { value: "pension", label: "Pension" },
  { value: "property", label: "Property" },
  { value: "other_asset", label: "Other asset" },
  { value: "directors_loan", label: "Director's loan" },
];

export default function PersonalFinancePage() {
  const { user, gated, redirecting } = useRequireAuth();
  const [accounts, setAccounts] = useState<FinanceAccount[]>([]);
  const [liabilities, setLiabilities] = useState<FinanceLiability[]>([]);
  const [overview, setOverview] = useState<FinanceOverview | null>(null);
  const [, setSnapshot] = useState<PersonalFinanceSnapshot | null>(null);
  const [activeBudget, setActiveBudget] = useState<BudgetPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [snapshotForm, setSnapshotForm] = useState({
    monthly_income_gbp: "",
    monthly_spending_gbp: "",
    household_bills_gbp: "",
    debt_repayments_gbp: "",
  });
  const periodState = useFinancePeriod({
    fixedScope: "personal",
    defaultPeriod: "mtd",
    preferDefaultPeriod: true,
  });
  const [periodFlow, setPeriodFlow] = useState<PeriodFlowSummary | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [debtPlan, setDebtPlan] = useState<DebtStrategy | null>(null);
  const [cashflowPlan, setCashflowPlan] = useState<ScopedCashflowPlan | null>(null);

  const load = useCallback(async () => {
    const errors: string[] = [];

    // Position must not depend on overview period-flows, period-flow, or budgets —
    // those can time out independently and previously blanked every tile.
    const [acctsSettled, debtsSettled, overviewSettled] = await Promise.allSettled([
      apiClient.get<unknown>("/finance/accounts?scope=personal"),
      apiClient.get<unknown>("/finance/liabilities?scope=personal"),
      apiClient.get<unknown>(
        `/finance/overview?fresh=1&personal_period=${periodState.period}&business_period=${periodState.period}`,
      ),
    ]);
    if (acctsSettled.status === "fulfilled") {
      setAccounts(parseFinanceAccounts(acctsSettled.value));
    } else {
      errors.push(
        acctsSettled.reason instanceof Error
          ? acctsSettled.reason.message
          : "Failed to load personal accounts",
      );
    }
    if (debtsSettled.status === "fulfilled") {
      setLiabilities(parseFinanceLiabilities(debtsSettled.value));
    } else {
      errors.push(
        debtsSettled.reason instanceof Error
          ? debtsSettled.reason.message
          : "Failed to load personal liabilities",
      );
    }
    if (overviewSettled.status === "fulfilled") {
      const parsedOverview = financeOverviewSchema.safeParse(overviewSettled.value);
      setOverview(parsedOverview.success ? parsedOverview.data : null);
    } else {
      setOverview(null);
      errors.push(
        overviewSettled.reason instanceof Error
          ? overviewSettled.reason.message
          : "Failed to load overview",
      );
    }

    // Paint Position from accounts/overview immediately — don't wait on period/budget.
    setHydrated(true);
    setError(errors.length ? errors[0] : null);

    try {
      const flow = await apiClient.get<unknown>(
        `/finance/period-flow?period=${periodState.period}&scope=personal`,
      );
      const parsedFlow = periodFlowSummarySchema.safeParse(flow);
      setPeriodFlow(parsedFlow.success ? parsedFlow.data : null);
    } catch (err) {
      setPeriodFlow(null);
      errors.push(err instanceof Error ? err.message : "Failed to load period flow");
    }

    try {
      const budget = await apiClient
        .get<unknown>("/finance/budgets/active?scope=personal")
        .catch(() => null);
      const parsedBudget = budgetPlanSchema.safeParse(budget);
      setActiveBudget(parsedBudget.success ? parsedBudget.data : null);
    } catch {
      setActiveBudget(null);
    }

    try {
      const strat = await apiClient.get<unknown>("/finance/debts/strategy/personal");
      const parsedStrat = debtStrategySchema.safeParse(strat);
      setDebtPlan(parsedStrat.success ? parsedStrat.data : null);
    } catch {
      setDebtPlan(null);
    }

    try {
      const plans = await apiClient.get<unknown>("/finance/cashflow/plans?months=3");
      const parsedPlans = dualCashflowPlansSchema.safeParse(plans);
      setCashflowPlan(parsedPlans.success ? parsedPlans.data.personal : null);
    } catch {
      setCashflowPlan(null);
    }

    try {
      const snaps = await apiClient.get<unknown>("/finance/snapshots/personal");
      const parsed = z.array(personalFinanceSnapshotSchema).safeParse(snaps);
      if (parsed.success) {
        const current =
          parsed.data.find((item) => isCurrentMonthSnapshot(item.snapshot_date)) ?? null;
        setSnapshot(current);
        if (current) {
          setSnapshotForm({
            monthly_income_gbp: String(current.monthly_income_gbp),
            monthly_spending_gbp: String(current.monthly_spending_gbp),
            household_bills_gbp: String(current.household_bills_gbp),
            debt_repayments_gbp: String(current.debt_repayments_gbp),
          });
        }
      }
    } catch (err) {
      errors.push(err instanceof Error ? err.message : "Failed to load snapshots");
    }

    setError(errors.length ? errors[0] : null);
  }, [periodState.period]);


  useFinanceReload(load, Boolean(user));
  const { refreshing } = useFinanceBackgroundLiveRefresh(user);

  async function saveSnapshot(event: React.FormEvent) {
    event.preventDefault();
    if (!canWrite(user) || saving) return;
    setSaving(true);
    try {
      const payload = {
        snapshot_date: currentMonthKey(),
        monthly_income_gbp: parseGbp(snapshotForm.monthly_income_gbp),
        monthly_spending_gbp: parseGbp(snapshotForm.monthly_spending_gbp),
        household_bills_gbp: parseGbp(snapshotForm.household_bills_gbp),
        debt_repayments_gbp: parseGbp(snapshotForm.debt_repayments_gbp),
      };
      if (Object.values(payload).some((value) => typeof value === "number" && Number.isNaN(value))) {
        throw new Error("Enter valid amounts for the monthly snapshot");
      }
      await apiClient.post("/finance/snapshots/personal", payload);
      setStatus("Saved");
      notifyFinanceChanged();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save snapshot");
    } finally {
      setSaving(false);
    }
  }

  if (gated) return <AuthLoadingShell redirecting={redirecting} />;

  // Prefer Overview totals (same Neon compute as the dashboard) so Position
  // cannot drift or blank when a client-side re-sum misses rows.
  const cashFromAccounts = accounts
    .filter((a) => a.account_type === "current")
    .reduce((s, a) => s + Math.max(a.balance_gbp, 0), 0);
  const overdraftFromAccounts = accounts
    .filter((a) => a.account_type === "current" && a.balance_gbp < 0)
    .reduce((s, a) => s + Math.abs(a.balance_gbp), 0);
  const pensionFromAccounts = accounts
    .filter((a) => a.account_type === "pension")
    .reduce((s, a) => s + a.balance_gbp, 0);
  const propertyFromAccounts = accounts
    .filter((a) => a.account_type === "property")
    .reduce((s, a) => s + a.balance_gbp, 0);
  const otherAssets = accounts
    .filter((a) => a.account_type === "other_asset")
    .reduce((s, a) => s + a.balance_gbp, 0);

  const bank =
    overview?.personal_bank_balance_gbp
    ?? round2(cashFromAccounts - overdraftFromAccounts);
  const overdraft = overview?.personal_overdraft_gbp ?? overdraftFromAccounts;
  const pension = overview?.pension_value_gbp ?? pensionFromAccounts;
  const property = overview?.property_gbp ?? propertyFromAccounts;
  // personal_bank = positive pots − overdraft, so pots = bank + overdraft.
  const positivePots = overview
    ? round2((overview.personal_bank_balance_gbp ?? 0) + (overview.personal_overdraft_gbp ?? 0))
    : cashFromAccounts;
  const assets = round2(positivePots + pension + property + otherAssets);

  const activePersonalDebts = liabilities.filter(
    (d) => d.is_active && d.scope === "personal" && d.debt_type !== "directors_loan",
  );
  const personalDebtsFromList = activePersonalDebts.reduce((s, d) => s + d.balance_gbp, 0);
  const personalDebts = overview?.total_personal_debt_gbp ?? personalDebtsFromList;
  const mortgage =
    overview?.mortgage_balance_gbp
    ?? activePersonalDebts
      .filter((d) => d.debt_type === "mortgage")
      .reduce((s, d) => s + d.balance_gbp, 0);
  const creditCards =
    overview?.personal_credit_card_balances_gbp
    ?? activePersonalDebts
      .filter((d) => d.debt_type === "credit_card")
      .reduce((s, d) => s + d.balance_gbp, 0);
  const personalLoans =
    overview?.personal_loan_balances_gbp
    ?? activePersonalDebts
      .filter((d) => d.debt_type === "loan")
      .reduce((s, d) => s + d.balance_gbp, 0);
  const directorOwes =
    overview?.director_owes_company_gbp
    ?? liabilities
      .filter(
        (d) =>
          d.is_active
          && d.debt_type === "directors_loan"
          && d.dla_direction === "director_owes_company",
      )
      .reduce((s, d) => s + d.balance_gbp, 0);
  const companyOwes =
    overview?.company_owes_director_gbp
    ?? liabilities
      .filter(
        (d) =>
          d.is_active
          && d.debt_type === "directors_loan"
          && d.dla_direction !== "director_owes_company",
      )
      .reduce((s, d) => s + d.balance_gbp, 0);
  const usePeriod = Boolean(periodFlow && periodFlow.transaction_count > 0);
  const surplusValue = usePeriod
    ? periodFlow!.surplus_gbp
    : activeBudget
      ? activeBudget.totals.surplus_gbp
      : null;
  const surplusHint = !hydrated
    ? "Loading…"
    : usePeriod
      ? periodFlow!.coverage_note || `${periodFlow!.label} · stored transactions`
      : activeBudget
        ? "Typical personal budget plan surplus"
        : "No period transactions or active budget surplus yet";
  const incomeValue = !hydrated
    ? null
    : usePeriod
      ? periodFlow!.income_gbp
      : activeBudget
        ? activeBudget.income_gbp
        : null;
  const incomeHint = !hydrated
    ? "Loading…"
    : usePeriod
      ? periodFlow!.coverage_note || "Stored transactions"
      : activeBudget
        ? "Typical personal budget plan"
        : undefined;
  const spendingValue = !hydrated
    ? null
    : usePeriod
      ? periodFlow!.spending_gbp
      : activeBudget
        ? activeBudget.totals.total_spending_gbp
        : null;
  const spendingHint = !hydrated
    ? "Loading…"
    : usePeriod
      ? periodFlow!.coverage_note || "Stored transactions"
      : activeBudget
        ? "Typical personal budget plan"
        : undefined;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Personal Finance"
        description="Current accounts, pension, property, and the director's loan between you and the company."
      />
      {error ? <div className="mt-4"><ErrorBanner message={error} /></div> : null}
      {status ? <div className="mt-4"><SuccessBanner message={status} /></div> : null}
      <div className="mt-4">
        <SavedFiguresBanner refreshing={refreshing} />
      </div>
      <div className="mt-6">
        <FinancePeriodScopeControl
          period={periodState.period}
          onPeriodChange={periodState.setPeriod}
          showScope={false}
          coverageNote={periodFlow?.coverage_note || null}
        />
      </div>

      {/* Hero: this-period income / spend / surplus (period label is the control heading above) */}
      <section className="mt-8" aria-label="This period cashflow">
        <h2 className="solar-section-title">Income, spend &amp; surplus</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          For the selected window above. Source labelled on each tile.
        </p>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <MetricTile
            label={
              usePeriod
                ? `Personal income (${periodFlow!.label})`
                : activeBudget
                  ? "Personal planned income"
                  : "Personal monthly income"
            }
            value={incomeValue}
            positive
            hint={incomeHint}
          />
          <MetricTile
            label={
              usePeriod
                ? `Personal spending (${periodFlow!.label})`
                : activeBudget
                  ? "Personal planned spending"
                  : "Personal monthly spending"
            }
            value={spendingValue}
            hint={spendingHint}
          />
          <MetricTile
            label={
              usePeriod
                ? `Personal surplus (${periodFlow!.label})`
                : activeBudget
                  ? "Personal planned surplus"
                  : "Personal monthly surplus"
            }
            value={surplusValue}
            positive={(surplusValue ?? 0) >= 0}
            warning={(surplusValue ?? 0) < 0}
            hint={surplusHint}
          />
        </div>
      </section>

      <div className="mt-6">
        <FinanceDataGapsBanner gaps={overview?.data_gaps} />
      </div>

      {/* Debt stack */}
      <section className="mt-8" aria-label="Personal debt stack">
        <h2 className="solar-section-title">Personal debt stack</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Cards, loans, mortgage, and overdraft as one pile. Director&apos;s loan is separate —
          not a lender to repay.
        </p>
        {!hydrated ? (
          <p className="mt-4 text-sm text-[var(--muted)]">Loading debts…</p>
        ) : (
          <div className="mt-4">
            <DebtStackPanel
              scope="personal"
              lines={{
                creditCardsGbp: creditCards,
                loansGbp: personalLoans,
                mortgageGbp: mortgage,
                overdraftGbp: overdraft,
                registerDebtGbp: personalDebts,
                mortgageConfigured: mortgage > 0 || overview?.mortgage_configured,
              }}
              dla={{
                directorOwesCompanyGbp: directorOwes,
                companyOwesDirectorGbp: companyOwes,
              }}
            />
          </div>
        )}
      </section>

      <section className="mt-8" aria-label="Personal debt reduction plan">
        <h2 className="solar-section-title">Debt reduction plan</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Personal stack only — business debts stay on Business. Director&apos;s loan is not a
          debt to repay.
        </p>
        <div className="mt-4 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
          <DebtReductionPlanPanel plan={debtPlan} loading={!hydrated} />
        </div>
      </section>

      <section className="mt-8" aria-label="Personal cashflow plan">
        <h2 className="solar-section-title">Cashflow plan</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          This month and the next two. Flags if the personal current account would go past the
          £3,000 overdraft facility.
        </p>
        <div className="mt-4 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
          <CashflowPlanPanel plan={cashflowPlan} loading={!hydrated} title="Personal cashflow" />
        </div>
      </section>

      {/* Position */}
      <section className="mt-8" aria-label="Personal position">
        <h2 className="solar-section-title">Position</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Bank and assets now. Overdraft is listed in the debt stack above; bank stays net.
        </p>
        {!hydrated ? (
          <p className="mt-4 text-sm text-[var(--muted)]">Loading position…</p>
        ) : (
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <MetricTile
            label="Personal bank"
            value={bank}
            warning={bank < 0 || overdraft > 0}
            hint={
              overdraft > 0
                ? `Net of overdraft ${formatGbp(overdraft)} (also in personal debt stack)`
                : "Current accounts (net of overdraft) — same as Overview"
            }
          />
          <MetricTile
            label="Personal assets"
            value={assets}
            hint="Pension + house share + other assets + positive personal cash"
          />
          <MetricTile
            label="Personal pension"
            value={pension}
            positive
            hint={pension > 0 ? "Included in personal net worth" : "Add the pot here so net worth includes it"}
          />
          <MetricTile
            label="Personal house (your half)"
            value={property > 0 ? property : null}
            positive={property > 0}
            hint="Your half of £700,000. Other half ignored."
          />
        </div>
        )}
      </section>

      <p className="mt-6 text-sm text-[var(--muted)]">
        The live app records your stated pension pot and personal mortgage
        half-share on first start. Edit those rows if the figures change.
        Director&apos;s loan direction follows the liability register (Robert
        owes the company, or the company owes Robert).
      </p>

      <div className="mt-8">
        <PlComparePanel scope="personal" title="Personal profit & loss compare" />
      </div>

      <section className="mt-8">
        <h2 className="solar-section-title">Accounts</h2>
        <AccountManager
          scope="personal"
          accounts={accounts}
          types={ACCOUNT_OPTIONS}
          canEdit={canWrite(user)}
          loading={!hydrated}
          onChanged={load}
          onError={setError}
          onNotice={setStatus}
        />
      </section>
      {canWrite(user) ? (
        <section className="mt-8">
          <h2 className="solar-section-title">Monthly snapshot ({currentMonthKey()})</h2>
          <form
            onSubmit={(event) => void saveSnapshot(event)}
            className="mt-3 grid gap-3 rounded-2xl border border-[var(--border)] p-4 sm:grid-cols-2 lg:grid-cols-5"
          >
            {(
              [
                ["monthly_income_gbp", "Income"],
                ["monthly_spending_gbp", "Spending"],
                ["household_bills_gbp", "Household bills"],
                ["debt_repayments_gbp", "Debt repayments"],
              ] as const
            ).map(([key, label]) => (
              <input
                key={key}
                className="solar-input"
                placeholder={label}
                value={snapshotForm[key]}
                onChange={(event) => setSnapshotForm({ ...snapshotForm, [key]: event.target.value })}
                required
              />
            ))}
            <button type="submit" className="solar-btn-primary" disabled={saving}>
              {saving ? "Saving…" : "Save snapshot"}
            </button>
          </form>
        </section>
      ) : null}
    </AppShell>
  );
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}
