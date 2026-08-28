"use client";

import Link from "next/link";
import { useState } from "react";

import { ActiveBudgetsBreakdown } from "@/components/finance/ActiveBudgetsBreakdown";
import { DebtStackPanel, debtStackTotal } from "@/components/finance/DebtStackPanel";
import { FinanceDataGapsBanner } from "@/components/finance/FinanceDataGapsBanner";
import { InsightCard } from "@/components/finance/InsightCard";
import { MetricTile } from "@/components/finance/MetricTile";
import { COMPANY_NAME, COMPANY_SHORT, PERSONAL_NAME, monthlyFlowHint } from "@/lib/finance-branding";
import { formatSafeSpendStatus } from "@/lib/finance-labels";
import type { FinanceOverview } from "@/lib/finance-schemas";
import { formatGbp } from "@/lib/money";

type FinanceOverviewViewProps = {
  overview: FinanceOverview;
  onDismissInsight?: (id: number) => void;
};

function flowLabel(prefix: string, periodLabel?: string | null) {
  return periodLabel ? `${prefix} (${periodLabel})` : prefix;
}

const HOUSE_HINT = "Your half of £700,000. Other half ignored.";
const COMBINED_LABEL = "Combined (personal + company, director's loan counted once)";

export function FinanceOverviewView({ overview, onDismissInsight }: FinanceOverviewViewProps) {
  const [scopeView, setScopeView] = useState<"combined" | "personal" | "business">("combined");
  const [showSafeCalc, setShowSafeCalc] = useState(false);
  const financeInsights = overview.insights.filter((item) => item.category !== "energy");
  const attention = financeInsights.filter(
    (item) => item.severity === "warning" || item.severity === "critical",
  );
  const recommendations = financeInsights.filter((item) => item.severity === "info");
  const upcoming = overview.upcoming_payments ?? [];
  // Always derive from the same bank figures shown in the hint — never trust a
  // stale cached cash_available_gbp that still equals positive pots only.
  const cashAvailable =
    Math.round(
      ((overview.personal_bank_balance_gbp ?? 0) + (overview.business_bank_balance_gbp ?? 0)) *
        100,
    ) / 100;
  const noCash =
    overview.personal_bank_balance_gbp === 0 && overview.business_bank_balance_gbp === 0;
  const hasPersonalOverdraft = (overview.personal_overdraft_gbp ?? 0) > 0;
  const hasBusinessOverdraft = (overview.business_overdraft_gbp ?? 0) > 0;
  const propertyMissing =
    (overview.property_gbp ?? 0) <= 0 && (overview.mortgage_balance_gbp ?? 0) > 0;
  const safe = overview.safe_to_spend ?? {};
  const personalSafe = safe.personal;
  const businessSafe = safe.business;
  const combinedSafe = safe.combined;
  const personalFlow = overview.personal_period_flow;
  const businessFlow = overview.business_period_flow;
  const useLedgerPeriod = Boolean(personalFlow && personalFlow.transaction_count > 0);
  const budgetSurplus = overview.active_budget?.surplus_gbp;
  const periodIncome = useLedgerPeriod
    ? personalFlow!.income_gbp
    : overview.monthly_flow_source === "open_banking"
      ? null
      : overview.monthly_income_gbp;
  const periodSpending = useLedgerPeriod
    ? personalFlow!.spending_gbp
    : overview.monthly_flow_source === "open_banking"
      ? null
      : overview.monthly_spending_gbp;
  // Prefer period ledger, then typical budget — never a thin OB 30-day window as surplus.
  const periodSurplus = useLedgerPeriod
    ? personalFlow!.surplus_gbp
    : overview.monthly_flow_source === "budget"
      ? (budgetSurplus ?? overview.monthly_surplus_gbp)
      : overview.monthly_flow_source === "open_banking"
        ? (budgetSurplus ?? null)
        : overview.monthly_flow_source === "none"
          ? null
          : overview.monthly_surplus_gbp;
  const periodFlowHint = useLedgerPeriod
    ? (personalFlow!.coverage_note || `${personalFlow!.label} · stored transactions`)
    : overview.monthly_flow_source === "budget"
      ? monthlyFlowHint("budget")
      : monthlyFlowHint(overview.monthly_flow_source);
  const hasPeriodFlow =
    useLedgerPeriod
    || overview.monthly_flow_source === "budget"
    || overview.monthly_flow_source === "cashflow"
    || overview.monthly_flow_source === "transactions"
    || (overview.monthly_flow_source === "snapshot" && periodSurplus != null);
  const incomeLabel = useLedgerPeriod
    ? flowLabel("Personal income", personalFlow!.label)
    : overview.monthly_flow_source === "budget"
      ? "Personal planned income"
      : "Personal monthly income";
  const spendingLabel = useLedgerPeriod
    ? flowLabel("Personal spending", personalFlow!.label)
    : overview.monthly_flow_source === "budget"
      ? "Personal planned spending"
      : "Personal monthly spending";
  const surplusLabel = useLedgerPeriod
    ? flowLabel("Personal surplus", personalFlow!.label)
    : overview.monthly_flow_source === "budget"
      ? "Personal planned surplus"
      : "Personal monthly surplus";
  const surplusHint = useLedgerPeriod
    ? periodFlowHint
    : overview.monthly_flow_source === "budget"
      ? "Typical personal budget plan surplus"
      : periodFlowHint;
  const periodSectionTitle = useLedgerPeriod
    ? `This period · ${personalFlow!.label}`
    : "This period flow";

  const showPersonal = scopeView === "combined" || scopeView === "personal";
  const showBusiness = scopeView === "combined" || scopeView === "business";
  const showCombined = scopeView === "combined";

  const personalStack = {
    creditCardsGbp: overview.personal_credit_card_balances_gbp ?? 0,
    loansGbp: overview.personal_loan_balances_gbp ?? 0,
    mortgageGbp: overview.mortgage_balance_gbp,
    overdraftGbp: overview.personal_overdraft_gbp ?? 0,
    registerDebtGbp: overview.total_personal_debt_gbp,
    mortgageConfigured: overview.mortgage_configured,
  };
  const businessStack = {
    creditCardsGbp: overview.business_credit_card_balances_gbp ?? 0,
    loansGbp: overview.loan_balances_gbp ?? 0,
    overdraftGbp: overview.business_overdraft_gbp ?? 0,
    registerDebtGbp: overview.total_business_debt_gbp,
  };
  const personalStackTotal = debtStackTotal(personalStack);
  const businessStackTotal = debtStackTotal(businessStack);
  const combinedFromStacks = Math.round((personalStackTotal + businessStackTotal) * 100) / 100;
  const combinedExternal =
    overview.external_debt_gbp != null ? overview.external_debt_gbp : combinedFromStacks;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap gap-2" role="group" aria-label="Finance scope">
        {(["combined", "personal", "business"] as const).map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => setScopeView(item)}
            className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${
              scopeView === item
                ? "bg-emerald-600 text-white"
                : "border border-[var(--border)] text-[var(--muted)]"
            }`}
          >
            {item}
          </button>
        ))}
      </div>

      {/* 1. Hero — net worth by scope */}
      <section aria-label="Net worth by scope">
        <h2 className="solar-section-title">Net worth</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Personal and company positions first. Combined nets both ledgers and counts the
          director&apos;s loan once.
        </p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {showPersonal ? (
            <MetricTile
              label="Personal net worth"
              value={overview.personal_net_worth_gbp}
              positive={(overview.personal_net_worth_gbp ?? 0) >= 0}
              hint="Cash + pension + house share − personal debts, with director's loan as Robert's asset or liability"
            />
          ) : null}
          {showBusiness ? (
            <MetricTile
              label="Business / company position"
              value={overview.company_position_gbp}
              positive={(overview.company_position_gbp ?? 0) >= 0}
              hint="Company cash + debtors + tax reserves − business debts, with director's loan as receivable or payable"
            />
          ) : null}
          {showCombined ? (
            <MetricTile
              label={COMBINED_LABEL}
              value={overview.net_worth_estimate_gbp}
              positive={overview.net_worth_estimate_gbp > 0}
              hint="Household + company; director's loan cancelled so the same IOU is not counted twice"
            />
          ) : null}
        </div>
        {propertyMissing ? (
          <p className="mt-3 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-100">
            Personal property value is not set but a personal mortgage is recorded — personal and
            combined net worth will look too low until you add the house value on{" "}
            <Link href="/finance/personal" className="underline underline-offset-2">
              Personal
            </Link>{" "}
            (account type: Property).
          </p>
        ) : null}
      </section>

      {/* 2. This period flow */}
      <section aria-label="This period flow">
        <h2 className="solar-section-title">{periodSectionTitle}</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          {useLedgerPeriod
            ? `Income, spend, and surplus from stored transactions. ${periodFlowHint}.`
            : `Personal household cashflow. ${periodFlowHint}.`}{" "}
          Source labelled on each tile.
        </p>
        {showPersonal ? (
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <MetricTile
              label={incomeLabel}
              value={hasPeriodFlow ? periodIncome : null}
              positive
              hint={periodFlowHint}
            />
            <MetricTile
              label={spendingLabel}
              value={hasPeriodFlow ? periodSpending : null}
              hint={periodFlowHint}
            />
            <MetricTile
              label={surplusLabel}
              value={hasPeriodFlow ? periodSurplus : null}
              positive={(periodSurplus ?? 0) >= 0}
              warning={(periodSurplus ?? 0) < 0}
              hint={surplusHint}
            />
          </div>
        ) : null}
        {showBusiness && businessFlow ? (
          <div className="mt-6">
            <h3 className="text-sm font-semibold">
              {COMPANY_SHORT} P&amp;L · {businessFlow.label}
            </h3>
            <p className="mt-1 text-xs text-[var(--muted)]">
              {businessFlow.coverage_note
                || `${businessFlow.date_from} to ${businessFlow.date_to} · stored transactions`}
            </p>
            <div className="mt-3 grid gap-4 sm:grid-cols-3">
              <MetricTile
                label={flowLabel("Business turnover", businessFlow.label)}
                value={businessFlow.transaction_count > 0 ? businessFlow.income_gbp : null}
                positive
                hint={businessFlow.coverage_note || "Stored business credits"}
              />
              <MetricTile
                label={flowLabel("Business expenses", businessFlow.label)}
                value={businessFlow.transaction_count > 0 ? businessFlow.spending_gbp : null}
                hint={businessFlow.coverage_note || "Stored business debits"}
              />
              <MetricTile
                label={flowLabel("Business surplus", businessFlow.label)}
                value={businessFlow.transaction_count > 0 ? businessFlow.surplus_gbp : null}
                positive={businessFlow.surplus_gbp >= 0}
                warning={businessFlow.surplus_gbp < 0}
                hint={businessFlow.coverage_note || "Income minus spending"}
              />
            </div>
          </div>
        ) : null}
        {showPersonal && !useLedgerPeriod && personalFlow === undefined ? (
          <p className="mt-3 text-xs text-[var(--muted)]">
            Household bills{" "}
            {overview.monthly_flow_source === "none"
              ? "—"
              : formatGbp(overview.household_bills_gbp)}
            {overview.monthly_flow_source === "budget"
              ? " · not set on the budget plan — use a snapshot for bills"
              : ""}
          </p>
        ) : null}
      </section>

      <FinanceDataGapsBanner gaps={overview.data_gaps} />

      {/* 3. Debt stacks — two piles, then a combined summary (not a third pile) */}
      <section aria-label="Debt stacks">
        <h2 className="solar-section-title">Debt stacks</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Personal and company debts as two separate piles. Groups inside each pile are
          subsets. Combined is only a summary — director&apos;s loan cancels once and is
          never a third pile of debt.
        </p>
        <div className={`mt-4 grid gap-6 ${showPersonal && showBusiness ? "lg:grid-cols-2" : ""}`}>
          {showPersonal ? (
            <DebtStackPanel
              scope="personal"
              lines={personalStack}
              dla={{
                directorOwesCompanyGbp: overview.director_owes_company_gbp ?? 0,
                companyOwesDirectorGbp: overview.company_owes_director_gbp ?? 0,
              }}
            />
          ) : null}
          {showBusiness ? (
            <DebtStackPanel
              scope="business"
              lines={businessStack}
              dla={{
                directorOwesCompanyGbp: overview.director_owes_company_gbp ?? 0,
                companyOwesDirectorGbp: overview.company_owes_director_gbp ?? 0,
              }}
            />
          ) : null}
        </div>
        {showCombined ? (
          <div className="mt-4 rounded-2xl border border-dashed border-[var(--border)] bg-[var(--surface)] p-4">
            <p className="text-[0.65rem] font-bold uppercase tracking-[0.14em] text-[var(--muted)]">
              Combined summary
            </p>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Adds the two stacks. Director&apos;s loan is cancelled in combined net worth and
              excluded here — not an extra debt on top.
            </p>
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <MetricTile
                label="Combined cash available"
                value={cashAvailable}
                warning={cashAvailable < 0}
                hint={`${formatGbp(overview.personal_bank_balance_gbp)} personal · ${formatGbp(overview.business_bank_balance_gbp)} company (net of overdrafts)`}
              />
              <MetricTile
                label="Combined external debt"
                value={combinedExternal}
                warning={combinedExternal > 0}
                hint={`${formatGbp(personalStackTotal)} personal stack · ${formatGbp(businessStackTotal)} business stack. Excludes director's loan ${formatGbp(overview.directors_loan_gbp)}.`}
              />
            </div>
            {(overview.monthly_interest_incomplete || (overview.monthly_interest_gbp ?? 0) > 0) ? (
              <div className="mt-4">
                <MetricTile
                  label="Combined est. monthly interest"
                  value={
                    overview.monthly_interest_incomplete && (overview.monthly_interest_gbp ?? 0) === 0
                      ? null
                      : overview.monthly_interest_gbp
                  }
                  warning={
                    Boolean(overview.monthly_interest_incomplete) ||
                    (overview.monthly_interest_gbp ?? 0) >= 50
                  }
                  hint={
                    overview.monthly_interest_incomplete && (overview.monthly_interest_gbp ?? 0) === 0
                      ? "Incomplete — APR required for interest forecast"
                      : overview.monthly_interest_incomplete
                        ? "Incomplete — from recorded APRs only; some debts still need APR"
                        : "From recorded annual APRs on Debts"
                  }
                />
              </div>
            ) : null}
          </div>
        ) : null}
      </section>

      {/* 4. Position — bank, house, pension, VAT (debts live in stacks above) */}
      <section aria-label="Position">
        <h2 className="solar-section-title">Position</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Cash and assets now. Overdrafts are listed in the debt stacks above; bank tiles stay
          net of overdraft.
        </p>

        <div className={`mt-6 grid gap-6 ${showPersonal && showBusiness ? "lg:grid-cols-2" : ""}`}>
          {showPersonal ? (
            <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[0.65rem] font-bold uppercase tracking-[0.14em] text-emerald-700 dark:text-emerald-400">
                    Personal
                  </p>
                  <h3 className="mt-1 text-lg font-semibold">{PERSONAL_NAME}</h3>
                </div>
                <Link href="/finance/personal" className="solar-btn-ghost text-sm">
                  Open
                </Link>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <MetricTile
                  label="Personal bank"
                  value={overview.personal_bank_balance_gbp}
                  warning={overview.personal_bank_balance_gbp < 0 || hasPersonalOverdraft}
                  hint={
                    hasPersonalOverdraft
                      ? `Net of overdraft ${formatGbp(overview.personal_overdraft_gbp)} (also in personal debt stack)`
                      : "Current accounts only"
                  }
                />
                <MetricTile
                  label="Personal house (your half)"
                  value={propertyMissing ? null : overview.property_gbp}
                  positive={!propertyMissing && (overview.property_gbp ?? 0) > 0}
                  warning={propertyMissing}
                  hint={
                    propertyMissing
                      ? "Add the house value so personal net worth is not just the mortgage"
                      : HOUSE_HINT
                  }
                />
                <MetricTile
                  label="Personal pension"
                  value={overview.pension_configured === false ? null : overview.pension_value_gbp}
                  positive
                  hint={
                    overview.pension_configured === false
                      ? "Add a pension account to track this"
                      : undefined
                  }
                />
                <MetricTile
                  label="High-interest debt"
                  value={overview.high_interest_debt_gbp}
                  warning={(overview.high_interest_debt_gbp ?? 0) > 0}
                  hint="APR 15% or more across all debts — pay this first"
                />
                <MetricTile
                  label="Available credit"
                  value={
                    (overview.credit_limit_gbp ?? 0) <= 0 && (overview.available_credit_gbp ?? 0) <= 0
                      ? null
                      : overview.available_credit_gbp
                  }
                  hint={
                    (overview.credit_limit_gbp ?? 0) <= 0 && (overview.available_credit_gbp ?? 0) <= 0
                      ? "No credit limits recorded on cards or revolving facilities"
                      : "Unused revolving credit limits (all scopes)"
                  }
                />
                <MetricTile
                  label="Personal cash after bills"
                  value={overview.cash_after_bills_gbp}
                  positive={overview.cash_after_bills_gbp > 0}
                  warning={overview.cash_after_bills_gbp < 500}
                />
              </div>
            </div>
          ) : null}

          {showBusiness ? (
            <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[0.65rem] font-bold uppercase tracking-[0.14em] text-teal-700 dark:text-teal-400">
                    Business / company
                  </p>
                  <h3 className="mt-1 text-lg font-semibold">{COMPANY_NAME}</h3>
                </div>
                <Link href="/finance/business" className="solar-btn-ghost text-sm">
                  Open
                </Link>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <MetricTile
                  label="Business bank"
                  value={overview.business_bank_balance_gbp}
                  warning={overview.business_bank_balance_gbp < 0 || hasBusinessOverdraft}
                  hint={
                    hasBusinessOverdraft
                      ? `Net of overdraft ${formatGbp(overview.business_overdraft_gbp)} (also in business debt stack)`
                      : "Current accounts only — not personal cash"
                  }
                />
                <MetricTile
                  label="Business VAT pot"
                  value={overview.vat_reserve_gbp}
                  warning={overview.vat_reserve_warning}
                  hint={
                    overview.vat_reserve_warning
                      ? "VAT reserve appears low"
                      : "Cash in VAT pot (paid reserve — not QuickFile VAT liability)"
                  }
                />
                <MetricTile
                  label="Business corp tax reserve"
                  value={overview.corp_tax_reserve_gbp}
                  warning={overview.corp_tax_reserve_warning}
                  hint="Tax provision (not yet paid)"
                />
                <MetricTile
                  label="Business debtors"
                  value={overview.debtors_gbp}
                  positive={(overview.debtors_gbp ?? 0) > 0}
                  hint="Amounts owed to the company"
                />
              </div>
            </div>
          ) : null}
        </div>

        {noCash ? (
          <p className="mt-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm text-[var(--muted)]">
            No current-account balances yet. Connect Open Banking or QuickFile on{" "}
            <Link href="/finance/connect" className="underline underline-offset-2">
              Connect banks
            </Link>
            , or{" "}
            <Link href="/finance/import" className="underline underline-offset-2">
              import a statement
            </Link>
            , or add them on Personal and Company.
          </p>
        ) : null}
      </section>

      {/* 4. Budgets */}
      <ActiveBudgetsBreakdown />

      {attention.length > 0 ? (
        <section>
          <h2 className="solar-section-title">Needs attention</h2>
          <div className="mt-4 grid gap-3">
            {attention.map((insight) => (
              <InsightCard key={insight.id} insight={insight} onDismiss={onDismissInsight} />
            ))}
          </div>
        </section>
      ) : null}

      {upcoming.length > 0 ? (
        <section>
          <div className="flex items-center justify-between gap-3">
            <h2 className="solar-section-title">Due in the next 14 days</h2>
            <Link href="/finance/upcoming" className="solar-btn-ghost text-sm">
              Full calendar
            </Link>
          </div>
          <ul className="mt-4 space-y-2">
            {upcoming.map((item) => (
              <li
                key={`${item.name}-${item.due_date}`}
                className="flex flex-col gap-1 rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between"
              >
                <span>
                  {item.name}{" "}
                  <span className="text-[var(--muted)]">
                    · {item.scope === "business" ? COMPANY_NAME : PERSONAL_NAME} · {item.due_date}
                    {item.days_until === 0 ? " · today" : ` · in ${item.days_until} days`}
                  </span>
                </span>
                <span className="font-semibold tabular-nums">{formatGbp(item.amount_gbp)}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section>
        <div className="flex items-center justify-between gap-3">
          <h2 className="solar-section-title">Recommendations</h2>
          <Link href="/finance/reports" className="solar-btn-ghost text-sm">
            View reports
          </Link>
        </div>
        {recommendations.length === 0 && attention.length === 0 ? (
          <p className="mt-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-6 text-sm text-[var(--muted)]">
            No active alerts. Add accounts and a monthly snapshot on Personal or Company, or record
            debts to see what to pay next.
          </p>
        ) : recommendations.length === 0 ? (
          <p className="mt-4 text-sm text-[var(--muted)]">
            No extra recommendations beyond the items that need attention.
          </p>
        ) : (
          <div className="mt-4 grid gap-3">
            {recommendations.map((insight) => (
              <InsightCard key={insight.id} insight={insight} onDismiss={onDismissInsight} />
            ))}
          </div>
        )}
      </section>

      {/* Demoted: safe to spend — do not lead the page */}
      <details className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="solar-section-title">Safe to spend</h2>
            <span className="text-xs text-[var(--muted)]">Secondary · expand for details</span>
          </div>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Deterministic buffer calc — often thinner than period surplus (uses a short Open Banking
            income window). Prefer the period surplus above for the real picture.
            {personalSafe?.flow_note || combinedSafe?.flow_note
              ? ` ${personalSafe?.flow_note || combinedSafe?.flow_note}.`
              : ""}
          </p>
        </summary>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {showPersonal && personalSafe ? (
            <MetricTile
              label="Personal safe to spend"
              value={personalSafe.safe_to_spend_gbp}
              positive={personalSafe.safe_to_spend_gbp > 0}
              warning={personalSafe.status !== "HEALTHY"}
              hint={
                personalSafe.flow_source === "budget"
                  ? monthlyFlowHint("budget")
                  : personalSafe.flow_note || formatSafeSpendStatus(personalSafe.status)
              }
            />
          ) : null}
          {showBusiness && businessSafe ? (
            <MetricTile
              label="Business available cash"
              value={businessSafe.available_business_cash_gbp}
              positive={businessSafe.available_business_cash_gbp > 0}
              warning={businessSafe.status !== "HEALTHY"}
              hint={formatSafeSpendStatus(businessSafe.status)}
            />
          ) : null}
          {showCombined && combinedSafe ? (
            <MetricTile
              label="Combined discretionary"
              value={combinedSafe.safe_to_spend_gbp}
              positive={combinedSafe.safe_to_spend_gbp > 0}
              hint={
                combinedSafe.flow_source === "budget"
                  ? monthlyFlowHint("budget")
                  : formatSafeSpendStatus(overview.cash_status ?? combinedSafe.status)
              }
            />
          ) : null}
        </div>
        <button
          type="button"
          className="mt-3 text-sm underline underline-offset-2"
          onClick={() => setShowSafeCalc((value) => !value)}
        >
          {showSafeCalc ? "Hide calculation" : "Show calculation"}
        </button>
        {showSafeCalc ? (
          <div className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
            {personalSafe?.breakdown ? (
              <pre className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3 text-xs">
                {JSON.stringify(personalSafe.breakdown, null, 2)}
              </pre>
            ) : null}
            {businessSafe?.breakdown ? (
              <pre className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3 text-xs">
                {JSON.stringify(businessSafe.breakdown, null, 2)}
              </pre>
            ) : null}
          </div>
        ) : null}
      </details>

      <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
        <h2 className="font-semibold">Quick links</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {[
            ["/finance/personal", "Personal"],
            ["/finance/business", COMPANY_SHORT],
            ["/finance/debts", "Debts"],
            ["/finance/cash-flow", "Cash flow"],
            ["/finance/budget", "Budget"],
            ["/finance/reports", "Reports"],
            ["/finance/connect", "Connect banks"],
          ].map(([href, label]) => (
            <Link key={href} href={href} className="solar-btn-ghost text-sm">
              {label}
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
