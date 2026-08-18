"use client";

import Link from "next/link";
import { useState } from "react";

import { ActiveBudgetCard } from "@/components/finance/ActiveBudgetCard";
import { InsightCard } from "@/components/finance/InsightCard";
import { MetricTile } from "@/components/finance/MetricTile";
import { COMPANY_NAME, COMPANY_SHORT, PERSONAL_NAME, monthlyFlowHint } from "@/lib/finance-branding";
import type { FinanceOverview } from "@/lib/finance-schemas";
import { formatGbp } from "@/lib/money";

type FinanceOverviewViewProps = {
  overview: FinanceOverview;
  onDismissInsight?: (id: number) => void;
};

function flowLabel(prefix: string, periodLabel?: string | null) {
  return periodLabel ? `${prefix} (${periodLabel})` : prefix;
}

export function FinanceOverviewView({ overview, onDismissInsight }: FinanceOverviewViewProps) {
  const [scopeView, setScopeView] = useState<"combined" | "personal" | "business">("combined");
  const [showSafeCalc, setShowSafeCalc] = useState(false);
  const financeInsights = overview.insights.filter((item) => item.category !== "energy");
  const attention = financeInsights.filter(
    (item) => item.severity === "warning" || item.severity === "critical",
  );
  const recommendations = financeInsights.filter((item) => item.severity === "info");
  const upcoming = overview.upcoming_payments ?? [];
  const cashAvailable = overview.cash_available_gbp ?? overview.available_cash_gbp ?? 0;
  const externalDebt = overview.external_debt_gbp ?? overview.total_personal_debt_gbp + overview.total_business_debt_gbp;
  const noCash =
    overview.personal_bank_balance_gbp === 0 && overview.business_bank_balance_gbp === 0;
  const hasOverdraft = (overview.personal_overdraft_gbp ?? 0) > 0;
  const budget = overview.active_budget;
  const propertyMissing =
    (overview.property_gbp ?? 0) <= 0 && (overview.mortgage_balance_gbp ?? 0) > 0;
  const safe = overview.safe_to_spend ?? {};
  const personalSafe = safe.personal;
  const businessSafe = safe.business;
  const combinedSafe = safe.combined;
  const personalFlow = overview.personal_period_flow;
  const businessFlow = overview.business_period_flow;
  const useLedgerPeriod = Boolean(personalFlow && personalFlow.transaction_count > 0);
  const periodIncome = useLedgerPeriod ? personalFlow!.income_gbp : overview.monthly_income_gbp;
  const periodSpending = useLedgerPeriod ? personalFlow!.spending_gbp : overview.monthly_spending_gbp;
  const periodSurplus = useLedgerPeriod ? personalFlow!.surplus_gbp : overview.monthly_surplus_gbp;
  const periodFlowHint = useLedgerPeriod
    ? (personalFlow!.coverage_note || `${personalFlow!.label} · stored transactions`)
    : monthlyFlowHint(overview.monthly_flow_source);
  const hasPeriodFlow = useLedgerPeriod || overview.monthly_flow_source !== "none";
  const incomeLabel = useLedgerPeriod
    ? flowLabel("Income", personalFlow!.label)
    : overview.monthly_flow_source === "budget"
      ? "Planned income"
      : "Monthly income";
  const spendingLabel = useLedgerPeriod
    ? flowLabel("Spending", personalFlow!.label)
    : overview.monthly_flow_source === "budget"
      ? "Planned spending"
      : "Monthly spending";
  const surplusLabel = useLedgerPeriod
    ? flowLabel("Surplus", personalFlow!.label)
    : overview.monthly_flow_source === "budget"
      ? "Planned surplus"
      : "Monthly surplus";

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap gap-2">
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

      <section>
        <h2 className="solar-section-title">Safe to spend</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Deterministic calculation from recorded income, bills, debt minimums and buffers — not an AI guess.
          {personalSafe?.flow_note || combinedSafe?.flow_note
            ? ` ${personalSafe?.flow_note || combinedSafe?.flow_note}.`
            : ""}
        </p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {(scopeView === "combined" || scopeView === "personal") && personalSafe ? (
            <MetricTile
              label="Safe to spend (personal)"
              value={personalSafe.safe_to_spend_gbp}
              positive={personalSafe.safe_to_spend_gbp > 0}
              warning={personalSafe.status !== "HEALTHY"}
              hint={
                personalSafe.flow_source === "budget"
                  ? monthlyFlowHint("budget")
                  : personalSafe.flow_note || personalSafe.status
              }
            />
          ) : null}
          {(scopeView === "combined" || scopeView === "business") && businessSafe ? (
            <MetricTile
              label="Available business cash"
              value={businessSafe.available_business_cash_gbp}
              positive={businessSafe.available_business_cash_gbp > 0}
              warning={businessSafe.status !== "HEALTHY"}
              hint={businessSafe.status}
            />
          ) : null}
          {scopeView === "combined" && combinedSafe ? (
            <MetricTile
              label="Combined discretionary"
              value={combinedSafe.safe_to_spend_gbp}
              positive={combinedSafe.safe_to_spend_gbp > 0}
              hint={
                combinedSafe.flow_source === "budget"
                  ? monthlyFlowHint("budget")
                  : overview.cash_status ?? combinedSafe.status
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
      </section>

      <section>
        <h2 className="solar-section-title">Balances</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Current snapshot — not filtered by the historical period above. Combined net worth is{" "}
          {PERSONAL_NAME}&apos;s personal assets plus {COMPANY_NAME}, minus external debt.
          Director&apos;s loan is shown separately and left out of the combined total so the same
          IOU is not counted twice.
        </p>
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
        {propertyMissing ? (
          <p className="mt-3 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-100">
            Property value is not set but a mortgage is recorded — combined net worth will look too
            low until you add the house value on{" "}
            <Link href="/finance/personal" className="underline underline-offset-2">
              Personal
            </Link>{" "}
            (account type: Property).
          </p>
        ) : null}
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <MetricTile
            label="Combined net worth"
            value={overview.net_worth_estimate_gbp}
            positive={overview.net_worth_estimate_gbp > 0}
            hint="Personal + company, excluding director's loan"
          />
          <MetricTile
            label="External debt"
            value={externalDebt}
            warning={externalDebt > 0}
            hint={`${formatGbp(overview.total_personal_debt_gbp)} personal · ${formatGbp(overview.total_business_debt_gbp)} company`}
          />
          <MetricTile
            label={useLedgerPeriod ? flowLabel("Cashflow", personalFlow!.label) : "Monthly cashflow"}
            value={hasPeriodFlow ? periodSurplus : null}
            positive={periodSurplus >= 0}
            warning={periodSurplus < 0}
            hint={
              useLedgerPeriod
                ? periodFlowHint
                : overview.monthly_flow_source === "budget"
                  ? "Budget plan estimate — not live cashflow"
                  : monthlyFlowHint(overview.monthly_flow_source)
            }
          />
          <MetricTile
            label="Cash available (current)"
            value={cashAvailable}
            warning={cashAvailable < 0}
            hint={`${formatGbp(overview.personal_bank_balance_gbp)} personal · ${formatGbp(overview.business_bank_balance_gbp)} company`}
          />
          <MetricTile
            label="Est. monthly interest"
            value={overview.monthly_interest_incomplete ? null : overview.monthly_interest_gbp}
            warning={Boolean(overview.monthly_interest_incomplete) || (overview.monthly_interest_gbp ?? 0) >= 50}
            hint={
              overview.monthly_interest_incomplete
                ? "APR required for interest forecast"
                : "From recorded annual APRs"
            }
          />
          <MetricTile
            label="High-interest debt"
            value={overview.high_interest_debt_gbp}
            warning={(overview.high_interest_debt_gbp ?? 0) > 0}
            hint="APR 15% or more — pay this first"
          />
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[0.65rem] font-bold uppercase tracking-[0.14em] text-emerald-700 dark:text-emerald-400">
                Personal
              </p>
              <h2 className="mt-1 text-lg font-semibold">{PERSONAL_NAME}</h2>
            </div>
            <Link href="/finance/personal" className="solar-btn-ghost text-sm">
              Open
            </Link>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <MetricTile
              label="Personal net worth"
              value={overview.personal_net_worth_gbp}
              positive={(overview.personal_net_worth_gbp ?? 0) >= 0}
              hint="Cash + pension − external debt, with director's loan as Robert's asset or liability"
            />
            <MetricTile
              label="Personal cash"
              value={overview.personal_bank_balance_gbp}
              warning={overview.personal_bank_balance_gbp < 0}
              hint="Current accounts only"
            />
            <MetricTile
              label="Personal debt"
              value={overview.total_personal_debt_gbp}
              warning={overview.total_personal_debt_gbp > 0}
            />
            <MetricTile
              label="Cash after bills"
              value={overview.cash_after_bills_gbp}
              positive={overview.cash_after_bills_gbp > 0}
              warning={overview.cash_after_bills_gbp < 500}
            />
            <MetricTile
              label="Pension (current)"
              value={overview.pension_configured === false ? null : overview.pension_value_gbp}
              positive
              hint={overview.pension_configured === false ? "Add a pension account to track this" : undefined}
            />
            <MetricTile
              label="Property"
              value={propertyMissing ? null : overview.property_gbp}
              positive={!propertyMissing && (overview.property_gbp ?? 0) > 0}
              warning={propertyMissing}
              hint={
                propertyMissing
                  ? "Add the house value so net worth is not just the mortgage"
                  : undefined
              }
            />
            <MetricTile
              label="Credit cards"
              value={overview.personal_credit_card_balances_gbp}
              warning={overview.personal_credit_card_balances_gbp > 0}
              hint="Personal cards only"
            />
            <MetricTile
              label="Available credit"
              value={overview.available_credit_gbp}
              hint="Unused card limits — add a limit on Personal or Debts"
            />
            {hasOverdraft ? (
              <MetricTile
                label="Personal overdraft"
                value={overview.personal_overdraft_gbp}
                warning
              />
            ) : (
              <MetricTile
                label="Mortgage"
                value={overview.mortgage_configured === false ? null : overview.mortgage_balance_gbp}
                hint={overview.mortgage_configured === false ? "Add a mortgage to track this" : undefined}
              />
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[0.65rem] font-bold uppercase tracking-[0.14em] text-teal-700 dark:text-teal-400">
                Company
              </p>
              <h2 className="mt-1 text-lg font-semibold">{COMPANY_NAME}</h2>
            </div>
            <Link href="/finance/business" className="solar-btn-ghost text-sm">
              Open
            </Link>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <MetricTile
              label="Company position"
              value={overview.company_position_gbp}
              positive={(overview.company_position_gbp ?? 0) >= 0}
              hint="Cash + debtors + tax reserves − external debt, with director's loan as receivable or payable"
            />
            <MetricTile
              label="Company cash"
              value={overview.business_bank_balance_gbp}
              warning={overview.business_bank_balance_gbp < 0}
              hint="Current accounts only — not personal cash"
            />
            <MetricTile
              label="Company liabilities"
              value={overview.total_business_debt_gbp}
              warning={overview.total_business_debt_gbp > 0}
            />
            <MetricTile
              label="Director's loan"
              value={overview.directors_loan_gbp}
              hint={
                (overview.director_owes_company_gbp ?? 0) > 0
                  ? `Robert owes the company ${formatGbp(overview.director_owes_company_gbp)}. Cancels in combined net worth.`
                  : (overview.company_owes_director_gbp ?? 0) > 0
                    ? `Company owes Robert ${formatGbp(overview.company_owes_director_gbp)}. Cancels in combined net worth.`
                    : "Internal Robert ↔ company. Excluded from combined net worth."
              }
            />
            <MetricTile
              label="VAT reserve (current)"
              value={overview.vat_reserve_gbp}
              warning={overview.vat_reserve_warning}
              hint={overview.vat_reserve_warning ? "VAT reserve appears low" : "Tax provision (not yet paid)"}
            />
            <MetricTile
              label="Corp tax reserve"
              value={overview.corp_tax_reserve_gbp}
              warning={overview.corp_tax_reserve_warning}
              hint="Tax provision (not yet paid)"
            />
            {(overview.business_overdraft_gbp ?? 0) > 0 ? (
              <MetricTile label="Company overdraft" value={overview.business_overdraft_gbp} warning />
            ) : (
              <MetricTile label="Loans" value={overview.loan_balances_gbp} />
            )}
          </div>
        </section>
      </div>

      <ActiveBudgetCard budget={budget} />

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
        <h2 className="solar-section-title">
          {useLedgerPeriod ? `Personal flow · ${personalFlow!.label}` : "Monthly flow"}
        </h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          {useLedgerPeriod
            ? `Personal household cashflow for ${personalFlow!.label} (${personalFlow!.date_from} to ${personalFlow!.date_to}). ${periodFlowHint}.`
            : `Personal household cashflow. ${periodFlowHint}.`}{" "}
          Company turnover for the business period is below when ledger history exists.
        </p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
            label="Household bills"
            value={
              useLedgerPeriod && personalFlow!.months_requested > 1
                ? null
                : overview.monthly_flow_source === "none"
                  ? null
                  : overview.household_bills_gbp
            }
            hint={
              useLedgerPeriod && personalFlow!.months_requested > 1
                ? "Bills are shown for a single-month window"
                : overview.monthly_flow_source === "budget"
                  ? "Not set on the budget plan — use a snapshot for bills"
                  : periodFlowHint
            }
          />
          <MetricTile
            label={surplusLabel}
            value={hasPeriodFlow ? periodSurplus : null}
            positive={periodSurplus >= 0}
            warning={periodSurplus < 0}
            hint={periodFlowHint}
          />
        </div>
        {businessFlow ? (
          <div className="mt-6">
            <h3 className="text-sm font-semibold">
              {COMPANY_SHORT} P&amp;L · {businessFlow.label}
            </h3>
            <p className="mt-1 text-xs text-[var(--muted)]">
              {businessFlow.coverage_note
                || `${businessFlow.date_from} to ${businessFlow.date_to} · stored transactions`}
            </p>
            <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <MetricTile
                label={flowLabel("Turnover", businessFlow.label)}
                value={businessFlow.transaction_count > 0 ? businessFlow.income_gbp : null}
                positive
                hint={businessFlow.coverage_note || "Stored business credits"}
              />
              <MetricTile
                label={flowLabel("Expenses", businessFlow.label)}
                value={businessFlow.transaction_count > 0 ? businessFlow.spending_gbp : null}
                hint={businessFlow.coverage_note || "Stored business debits"}
              />
              <MetricTile
                label={flowLabel("Surplus", businessFlow.label)}
                value={businessFlow.transaction_count > 0 ? businessFlow.surplus_gbp : null}
                positive={businessFlow.surplus_gbp >= 0}
                warning={businessFlow.surplus_gbp < 0}
                hint={businessFlow.coverage_note || "Income minus spending"}
              />
            </div>
          </div>
        ) : null}
      </section>

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
