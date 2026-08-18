"use client";

import { useEffect, useState } from "react";

import { AccountStatements } from "@/components/finance/AccountStatements";
import { FinancePeriodScopeControl } from "@/components/finance/FinancePeriodScopeControl";
import { ActiveBudgetCard } from "@/components/finance/ActiveBudgetCard";
import { BudgetVsActualPanel } from "@/components/finance/BudgetVsActualPanel";
import { FinanceHistoryCharts } from "@/components/finance/FinanceHistoryCharts";
import { MetricTile } from "@/components/finance/MetricTile";
import { PersonalReportPanel } from "@/components/finance/PersonalReportPanel";
import { PlComparePanel } from "@/components/finance/PlComparePanel";
import { PlHistoryChart } from "@/components/finance/PlHistoryChart";
import { QuickFileStatements } from "@/components/finance/QuickFileStatements";
import { FinanceExportPanel } from "@/components/finance/FinanceExportPanel";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner, SuccessBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { apiClient } from "@/lib/api-client";
import { useRequireAuth } from "@/lib/use-require-auth";
import { downloadTextFile, toCsv } from "@/lib/finance-export";
import {
  financeAccountSchema,
  financeLiabilitySchema,
  financeReportsSchema,
  type FinanceAccount,
  type FinanceLiability,
  type FinanceReports,
} from "@/lib/finance-schemas";
import { FINANCE_CHANGED_EVENT } from "@/lib/finance-events";
import { useFinancePeriod } from "@/lib/use-finance-period";
import { currentMonthKey, formatGbp, formatMonthLabel } from "@/lib/money";
import { z } from "zod";

export default function ReportsPage() {
  const { user, gated, redirecting } = useRequireAuth();
  const [reports, setReports] = useState<FinanceReports | null>(null);
  const [accounts, setAccounts] = useState<FinanceAccount[]>([]);
  const [debts, setDebts] = useState<FinanceLiability[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [month, setMonth] = useState(currentMonthKey());
  const [reloadNonce, setReloadNonce] = useState(0);
  const periodState = useFinancePeriod({ defaultScope: "both" });


  useEffect(() => {
    if (!user) return;
    const timer = window.setTimeout(() => {
      void (async () => {
        try {
          const [reportData, accountData, debtData] = await Promise.all([
            apiClient.get<unknown>(
              `/finance/reports?month=${month}&period=${periodState.period}&scope=${periodState.scope}`,
            ),
            apiClient.get<unknown>("/finance/accounts"),
            apiClient.get<unknown>("/finance/liabilities"),
          ]);
          setReports(financeReportsSchema.parse(reportData));
          setAccounts(z.array(financeAccountSchema).parse(accountData));
          setDebts(z.array(financeLiabilitySchema).parse(debtData));
          setError(null);
        } catch (err) {
          setReports(null);
          setError(
            err instanceof Error && err.message
              ? err.message
              : "Reports unavailable. Could not load the monthly report. Check your connection and try again.",
          );
        }
      })();
    }, 0);
    const onChanged = () => setReloadNonce((value) => value + 1);
    window.addEventListener(FINANCE_CHANGED_EVENT, onChanged);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener(FINANCE_CHANGED_EVENT, onChanged);
    };
  }, [user, month, reloadNonce, periodState.period, periodState.scope]);

  function exportSnapshot(format: "csv" | "json") {
    if (!reports) return;
    const snapshot = {
      month: reports.month,
      net_worth_gbp: reports.net_worth_gbp,
      total_debt_gbp: reports.total_debt_gbp,
      debt_reduction_gbp: reports.debt_reduction_gbp,
      accounts: accounts.map((item) => ({
        name: item.name,
        scope: item.scope,
        type: item.account_type,
        balance_gbp: item.balance_gbp,
      })),
      debts: debts.map((item) => ({
        name: item.name,
        scope: item.scope,
        type: item.debt_type,
        balance_gbp: item.balance_gbp,
        apr: item.interest_rate_pct,
      })),
      active_budget: reports.active_budget,
      budget_vs_actual: reports.budget_vs_actual,
    };
    if (format === "json") {
      downloadTextFile(`finance-snapshot-${month}.json`, JSON.stringify(snapshot, null, 2), "application/json");
    } else {
      downloadTextFile(
        `finance-snapshot-${month}.csv`,
        toCsv([
          {
            month: snapshot.month,
            net_worth_gbp: snapshot.net_worth_gbp,
            total_debt_gbp: snapshot.total_debt_gbp,
            debt_reduction_gbp: snapshot.debt_reduction_gbp,
          },
          ...snapshot.accounts.map((item) => ({
            month: snapshot.month,
            kind: "account",
            name: item.name,
            scope: item.scope,
            type: item.type,
            balance_gbp: item.balance_gbp,
          })),
          ...snapshot.debts.map((item) => ({
            month: snapshot.month,
            kind: "debt",
            name: item.name,
            scope: item.scope,
            type: item.type,
            balance_gbp: item.balance_gbp,
            apr: item.apr,
          })),
          ...(snapshot.budget_vs_actual?.lines ?? []).map((item) => ({
            month: snapshot.month,
            kind: "budget_vs_actual",
            name: item.category,
            scope: item.scope,
            budget_gbp: item.budget_gbp,
            actual_gbp: item.actual_gbp,
            variance_gbp: item.variance_gbp,
          })),
        ]),
        "text/csv",
      );
    }
    setStatus(`Exported ${format.toUpperCase()} snapshot`);
  }

  if (gated) return <AuthLoadingShell redirecting={redirecting} />;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Reports"
        description={`Monthly finance report for ${formatMonthLabel(month)}.`}
        actions={
          <input
            type="month"
            aria-label="Report month"
            className="solar-input text-sm"
            value={month}
            onChange={(event) => setMonth(event.target.value)}
          />
        }
      />
      {error ? (
        <div className="mt-4 space-y-3">
          <ErrorBanner message={error} />
          <button
            type="button"
            className="solar-btn-ghost text-sm"
            onClick={() => setReloadNonce((current) => current + 1)}
          >
            Try again
          </button>
        </div>
      ) : null}
      {status ? <div className="mt-4"><SuccessBanner message={status} /></div> : null}
      <div className="mt-6">
        <FinancePeriodScopeControl
          period={periodState.period}
          onPeriodChange={periodState.setPeriod}
          scope={periodState.scope}
          onScopeChange={periodState.setScope}
          coverageNote={
            [
              reports?.personal_period_flow?.coverage_note,
              reports?.business_period_flow?.coverage_note,
            ]
              .filter(Boolean)
              .join(" ")
            || null
          }
        />
      </div>
      {reports ? (
        <div className="mt-6 space-y-8">
          <ActiveBudgetCard budget={reports.active_budget} />
          <BudgetVsActualPanel
            variance={reports.budget_vs_actual}
            activeBudget={reports.active_budget}
          />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <MetricTile
              label="Net worth"
              value={reports.net_worth_gbp}
              hint={reports.net_worth_gbp == null ? "No recorded position for this month" : undefined}
            />
            <MetricTile
              label="Total debt"
              value={reports.total_debt_gbp}
              warning={reports.total_debt_gbp != null}
              hint={reports.total_debt_gbp == null ? "No recorded position for this month" : undefined}
            />
            <MetricTile
              label="Debt reduction"
              value={reports.debt_reduction_gbp}
              hint={
                reports.debt_reduction_available
                  ? "Against the last recorded month"
                  : "Against original balances where recorded"
              }
            />
          </div>
          <PersonalReportPanel report={reports.personal_report} />
          <div className="grid gap-8 lg:grid-cols-2">
            <PlComparePanel scope="personal" title="Personal P&L compare" />
            <PlComparePanel scope="business" title="Business P&L compare" />
          </div>
          <FinanceHistoryCharts reports={reports} />
          <section>
            <h2 className="solar-section-title">QuickFile statements</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">
              From the last stored QuickFile sync — not fetched live on this page.
            </p>
            <div className="mt-4">
              <QuickFileStatements
                reports={reports.quickfile_reports}
                fallbackPl={
                  reports.business_snapshot
                    ? {
                        turnover_gbp: reports.business_snapshot.turnover_gbp,
                        expenses_gbp: reports.business_snapshot.expenses_gbp,
                        net_profit_gbp: reports.business_snapshot.profit_estimate_gbp,
                      }
                    : undefined
                }
              />
            </div>
          </section>
          <section>
            <h2 className="solar-section-title">Company P&amp;L history</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Turnover, expenses, and profit from saved business snapshots.
            </p>
            <div className="mt-4">
              <PlHistoryChart points={reports.pl_history ?? []} />
            </div>
          </section>
          <section>
            <h2 className="solar-section-title">Account statements</h2>
            <div className="mt-4">
              <AccountStatements
                overview={{
                  property_gbp: accounts
                    .filter((item) => item.is_active && item.account_type === "property")
                    .reduce((sum, item) => sum + item.balance_gbp, 0),
                  mortgage_balance_gbp: debts
                    .filter((item) => item.is_active && item.debt_type === "mortgage")
                    .reduce((sum, item) => sum + item.balance_gbp, 0),
                }}
                accounts={accounts}
                liabilities={debts}
              />
            </div>
          </section>
          {reports.business_snapshot ? (
            <section>
              <h2 className="solar-section-title">Business snapshot</h2>
              <p className="mt-2 text-sm text-[var(--muted)]">
                Turnover {formatGbp(reports.business_snapshot.turnover_gbp)} · Expenses{" "}
                {formatGbp(reports.business_snapshot.expenses_gbp)} · Profit{" "}
                {formatGbp(reports.business_snapshot.profit_estimate_gbp)}
              </p>
            </section>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <button type="button" className="solar-btn-primary" onClick={() => exportSnapshot("csv")}>
              Export CSV
            </button>
            <button type="button" className="solar-btn-ghost" onClick={() => exportSnapshot("json")}>
              Export JSON
            </button>
          </div>
          <FinanceExportPanel />
        </div>
      ) : (
        error ? null : <p className="mt-8 text-sm text-[var(--muted)]">Loading reports…</p>
      )}
    </AppShell>
  );
}
