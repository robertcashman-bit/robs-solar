"use client";

import { useCallback, useState } from "react";
import { z } from "zod";

import { AccountManager } from "@/components/finance/AccountManager";
import { FinancePeriodScopeControl } from "@/components/finance/FinancePeriodScopeControl";
import { MetricTile } from "@/components/finance/MetricTile";
import { QuickFileStatements } from "@/components/finance/QuickFileStatements";
import { SavedFiguresBanner } from "@/components/finance/SavedFiguresBanner";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner, SuccessBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { apiClient } from "@/lib/api-client";
import { useRequireAuth } from "@/lib/use-require-auth";
import {
  businessFinanceSnapshotSchema,
  financeAccountSchema,
  periodFlowSummarySchema,
  quickFileReportsSchema,
  type BusinessFinanceSnapshot,
  type FinanceAccount,
  type PeriodFlowSummary,
  type QuickFileReports,
} from "@/lib/finance-schemas";
import { useFinanceBackgroundLiveRefresh } from "@/lib/use-finance-background-live-refresh";
import { useFinancePeriod } from "@/lib/use-finance-period";
import { useFinanceReload } from "@/lib/use-finance-reload";
import { currentMonthKey, isCurrentMonthSnapshot, parseGbp } from "@/lib/money";
import { notifyFinanceChanged } from "@/lib/finance-events";
import { canWrite } from "@/lib/permissions";

const ACCOUNT_OPTIONS = [
  { value: "current", label: "Current" },
  { value: "vat_reserve", label: "VAT reserve" },
  { value: "corp_tax_reserve", label: "Corp tax reserve" },
  { value: "loan", label: "Business loan / Funding Circle" },
  { value: "capital_on_tap", label: "Capital on Tap" },
  { value: "debtors", label: "Debtors" },
  { value: "creditors", label: "Creditors" },
  { value: "directors_loan", label: "Director's loan (owed to you)" },
  { value: "other_asset", label: "Other asset" },
];

export default function BusinessFinancePage() {
  const { user, gated, redirecting } = useRequireAuth();
  const [accounts, setAccounts] = useState<FinanceAccount[]>([]);
  const [snapshot, setSnapshot] = useState<BusinessFinanceSnapshot | null>(null);
  const [quickfileReports, setQuickfileReports] = useState<QuickFileReports | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [snapshotForm, setSnapshotForm] = useState({
    turnover_gbp: "",
    expenses_gbp: "",
    vat_reserve_gbp: "",
    corp_tax_reserve_gbp: "",
    debtors_gbp: "",
    creditors_gbp: "",
  });
  const periodState = useFinancePeriod({ fixedScope: "business" });
  const [periodFlow, setPeriodFlow] = useState<PeriodFlowSummary | null>(null);

  const load = useCallback(async () => {
    try {
      const [accts, snaps, qfReports, flow] = await Promise.all([
        apiClient.get<unknown>("/finance/accounts?scope=business"),
        apiClient.get<unknown>("/finance/snapshots/business"),
        apiClient.get<unknown>("/finance/integrations/quickfile/reports"),
        apiClient.get<unknown>(
          `/finance/period-flow?period=${periodState.period}&scope=business`,
        ),
      ]);
      const parsedFlow = periodFlowSummarySchema.safeParse(flow);
      setPeriodFlow(parsedFlow.success ? parsedFlow.data : null);
      setAccounts(z.array(financeAccountSchema).parse(accts));
      const parsed = z.array(businessFinanceSnapshotSchema).parse(snaps);
      const parsedReports = quickFileReportsSchema.safeParse(qfReports);
      setQuickfileReports(parsedReports.success ? parsedReports.data : null);
      const current = parsed.find((item) => isCurrentMonthSnapshot(item.snapshot_date)) ?? null;
      setSnapshot(current);
      if (current) {
        setSnapshotForm({
          turnover_gbp: String(current.turnover_gbp),
          expenses_gbp: String(current.expenses_gbp),
          vat_reserve_gbp: String(current.vat_reserve_gbp),
          corp_tax_reserve_gbp: String(current.corp_tax_reserve_gbp),
          debtors_gbp: String(current.debtors_gbp),
          creditors_gbp: String(current.creditors_gbp),
        });
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load business finance");
    }
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
        turnover_gbp: parseGbp(snapshotForm.turnover_gbp),
        expenses_gbp: parseGbp(snapshotForm.expenses_gbp),
        vat_reserve_gbp: parseGbp(snapshotForm.vat_reserve_gbp),
        corp_tax_reserve_gbp: parseGbp(snapshotForm.corp_tax_reserve_gbp),
        debtors_gbp: parseGbp(snapshotForm.debtors_gbp),
        creditors_gbp: parseGbp(snapshotForm.creditors_gbp),
      };
      if (Object.values(payload).some((value) => typeof value === "number" && Number.isNaN(value))) {
        throw new Error("Enter valid amounts for the monthly snapshot");
      }
      await apiClient.post("/finance/snapshots/business", payload);
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

  const bankBalance = accounts
    .filter((account) => account.account_type === "current")
    .reduce((sum, account) => sum + Math.max(account.balance_gbp, 0), 0);
  const directorsLoan = accounts
    .filter((account) => account.account_type === "directors_loan")
    .reduce((sum, account) => sum + account.balance_gbp, 0);
  const vatReserveAccounts = accounts.filter(
    (account) => account.account_type === "vat_reserve",
  );
  // Prefer the VAT pot account (QuickFile 1210) over snapshot, which may still
  // hold creditor VAT liability from older syncs.
  const vatReserveGbp =
    vatReserveAccounts.length > 0
      ? vatReserveAccounts.reduce((sum, account) => sum + account.balance_gbp, 0)
      : snapshot?.vat_reserve_gbp;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Business Finance"
        description="Turnover, expenses, tax reserves, and the director's loan the company owes you."
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
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricTile label="Business bank" value={bankBalance} hint="Positive current accounts" />
        <MetricTile
          label={
            periodFlow && periodFlow.transaction_count > 0
              ? `Business turnover (${periodFlow.label})`
              : "Business turnover (month)"
          }
          value={
            periodFlow && periodFlow.transaction_count > 0
              ? periodFlow.income_gbp
              : snapshot?.turnover_gbp
          }
          hint={
            periodFlow && periodFlow.transaction_count > 0
              ? periodFlow.coverage_note || "Stored transactions"
              : "Snapshot / QuickFile month"
          }
        />
        <MetricTile
          label={
            periodFlow && periodFlow.transaction_count > 0
              ? `Business expenses (${periodFlow.label})`
              : "Business expenses (month)"
          }
          value={
            periodFlow && periodFlow.transaction_count > 0
              ? periodFlow.spending_gbp
              : snapshot?.expenses_gbp
          }
          hint={
            periodFlow && periodFlow.transaction_count > 0
              ? periodFlow.coverage_note || "Stored transactions"
              : "Snapshot / QuickFile month"
          }
        />
        <MetricTile
          label={
            periodFlow && periodFlow.transaction_count > 0
              ? `Business profit (${periodFlow.label})`
              : "Business profit estimate"
          }
          value={
            periodFlow && periodFlow.transaction_count > 0
              ? periodFlow.surplus_gbp
              : snapshot?.profit_estimate_gbp
          }
          positive
          hint={
            periodFlow && periodFlow.transaction_count > 0
              ? periodFlow.coverage_note || "Stored transactions"
              : "Snapshot"
          }
        />
        <MetricTile label="Business VAT pot" value={vatReserveGbp} hint="Cash in VAT pot" />
        <MetricTile label="Business corp tax reserve" value={snapshot?.corp_tax_reserve_gbp} />
        <MetricTile label="Business debtors" value={snapshot?.debtors_gbp} />
        <MetricTile
          label="Business director's loan"
          value={directorsLoan}
          positive={directorsLoan > 0}
          hint="Owed to you — cancels in combined net worth"
        />
        <MetricTile label="Business cash to draw" value={snapshot?.cash_available_to_draw_gbp} />
      </div>
      <section className="mt-8">
        <h2 className="solar-section-title">Live QuickFile statements</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Pulled from QuickFile on sync (month and YTD columns). Multi-month period chips above
          use stored business transactions for the historical window — they do not invent a
          custom QuickFile report.
        </p>
        <div className="mt-4">
          <QuickFileStatements
            reports={quickfileReports}
            fallbackPl={
              snapshot
                ? {
                    turnover_gbp: snapshot.turnover_gbp,
                    expenses_gbp: snapshot.expenses_gbp,
                    net_profit_gbp: snapshot.profit_estimate_gbp,
                  }
                : undefined
            }
          />
        </div>
      </section>
      <section className="mt-8">
        <h2 className="solar-section-title">Accounts</h2>
        <AccountManager
          scope="business"
          accounts={accounts}
          types={ACCOUNT_OPTIONS}
          canEdit={canWrite(user)}
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
            className="mt-3 grid gap-3 rounded-2xl border border-[var(--border)] p-4 sm:grid-cols-2 lg:grid-cols-4"
          >
            {(
              [
                ["turnover_gbp", "Turnover"],
                ["expenses_gbp", "Expenses"],
                ["vat_reserve_gbp", "VAT reserve"],
                ["corp_tax_reserve_gbp", "Corp tax reserve"],
                ["debtors_gbp", "Debtors"],
                ["creditors_gbp", "Creditors"],
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
            <button type="submit" className="solar-btn-primary sm:col-span-2" disabled={saving}>
              {saving ? "Saving…" : "Save snapshot"}
            </button>
          </form>
        </section>
      ) : null}
    </AppShell>
  );
}
