"use client";

import { useCallback, useState } from "react";
import { z } from "zod";

import { AccountManager } from "@/components/finance/AccountManager";
import { FinancePeriodScopeControl } from "@/components/finance/FinancePeriodScopeControl";
import { MetricTile } from "@/components/finance/MetricTile";
import { MetricWithOfWhich } from "@/components/finance/OfWhichBreakdown";
import { PlComparePanel } from "@/components/finance/PlComparePanel";
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
  financeLiabilitySchema,
  periodFlowSummarySchema,
  quickFileReportsSchema,
  type BusinessFinanceSnapshot,
  type FinanceAccount,
  type FinanceLiability,
  type PeriodFlowSummary,
  type QuickFileReports,
} from "@/lib/finance-schemas";
import { useFinanceBackgroundLiveRefresh } from "@/lib/use-finance-background-live-refresh";
import { useFinancePeriod } from "@/lib/use-finance-period";
import { useFinanceReload } from "@/lib/use-finance-reload";
import { currentMonthKey, formatGbp, isCurrentMonthSnapshot, parseGbp } from "@/lib/money";
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
  const [liabilities, setLiabilities] = useState<FinanceLiability[]>([]);
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
  const periodState = useFinancePeriod({
    fixedScope: "business",
    defaultPeriod: "mtd",
    preferDefaultPeriod: true,
  });
  const [periodFlow, setPeriodFlow] = useState<PeriodFlowSummary | null>(null);

  const load = useCallback(async () => {
    try {
      const [accts, debts, snaps, flow] = await Promise.all([
        apiClient.get<unknown>("/finance/accounts?scope=business"),
        apiClient.get<unknown>("/finance/liabilities?scope=business"),
        apiClient.get<unknown>("/finance/snapshots/business"),
        apiClient.get<unknown>(
          `/finance/period-flow?period=${periodState.period}&scope=business`,
        ),
      ]);
      const parsedFlow = periodFlowSummarySchema.safeParse(flow);
      setPeriodFlow(parsedFlow.success ? parsedFlow.data : null);
      setAccounts(z.array(financeAccountSchema).parse(accts));
      setLiabilities(z.array(financeLiabilitySchema).parse(debts));
      const parsed = z.array(businessFinanceSnapshotSchema).parse(snaps);
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
      // Stored QuickFile statements after first paint — never block the page on live QF.
      void apiClient
        .get<unknown>("/finance/integrations/quickfile/reports")
        .then((qfReports) => {
          const parsedReports = quickFileReportsSchema.safeParse(qfReports);
          setQuickfileReports(parsedReports.success ? parsedReports.data : null);
        })
        .catch(() => {
          setQuickfileReports(null);
        });
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
  const overdraft = accounts
    .filter((account) => account.account_type === "current" && account.balance_gbp < 0)
    .reduce((sum, account) => sum + Math.abs(account.balance_gbp), 0);
  const directorsLoan = accounts
    .filter((account) => account.account_type === "directors_loan")
    .reduce((sum, account) => sum + account.balance_gbp, 0);
  const activeBusinessDebts = liabilities.filter(
    (d) => d.is_active && d.scope === "business" && d.debt_type !== "directors_loan",
  );
  const loanAccountBalance = accounts
    .filter(
      (a) =>
        a.is_active
        && (a.account_type === "loan" || a.account_type === "capital_on_tap"),
    )
    .reduce((sum, a) => sum + Math.max(a.balance_gbp, 0), 0);
  const businessLoansFromDebts = activeBusinessDebts
    .filter((d) => d.debt_type === "loan" || d.debt_type === "business_loan")
    .reduce((sum, d) => sum + d.balance_gbp, 0);
  // Prefer liability register; fall back to loan / Capital on Tap accounts.
  const businessLoans =
    businessLoansFromDebts > 0 ? businessLoansFromDebts : loanAccountBalance;
  const businessDebts =
    activeBusinessDebts.reduce((sum, d) => sum + d.balance_gbp, 0)
    || businessLoans;
  const vatReserveAccounts = accounts.filter(
    (account) => account.account_type === "vat_reserve",
  );
  // Prefer the VAT pot account (QuickFile 1210) over snapshot, which may still
  // hold creditor VAT liability from older syncs.
  const vatReserveGbp =
    vatReserveAccounts.length > 0
      ? vatReserveAccounts.reduce((sum, account) => sum + account.balance_gbp, 0)
      : snapshot?.vat_reserve_gbp;
  const usePeriod = Boolean(periodFlow && periodFlow.transaction_count > 0);
  const dlaHint =
    directorsLoan > 0
      ? "Company owes Robert — cancels in combined net worth"
      : directorsLoan < 0
        ? `Robert owes the company ${formatGbp(Math.abs(directorsLoan))}. Cancels in combined net worth.`
        : "Internal Robert ↔ company. Excluded from combined net worth.";

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Business Finance"
        description="Turnover, expenses, tax reserves, and company cash position."
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

      {/* Hero: MTD / selected period P&L (period label is the control heading above) */}
      <section className="mt-8" aria-label="This period cashflow">
        <h2 className="solar-section-title">Turnover, spend &amp; profit</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          For the selected window above. Source labelled on each tile.
        </p>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <MetricTile
            label={
              usePeriod
                ? `Business turnover (${periodFlow!.label})`
                : "Business turnover (month)"
            }
            value={usePeriod ? periodFlow!.income_gbp : snapshot?.turnover_gbp}
            positive
            hint={
              usePeriod
                ? periodFlow!.coverage_note || "Stored transactions"
                : "Snapshot / QuickFile month"
            }
          />
          <MetricTile
            label={
              usePeriod
                ? `Business expenses (${periodFlow!.label})`
                : "Business expenses (month)"
            }
            value={usePeriod ? periodFlow!.spending_gbp : snapshot?.expenses_gbp}
            hint={
              usePeriod
                ? periodFlow!.coverage_note || "Stored transactions"
                : "Snapshot / QuickFile month"
            }
          />
          <MetricTile
            label={
              usePeriod
                ? `Business profit (${periodFlow!.label})`
                : "Business profit estimate"
            }
            value={usePeriod ? periodFlow!.surplus_gbp : snapshot?.profit_estimate_gbp}
            positive={(usePeriod ? periodFlow!.surplus_gbp : snapshot?.profit_estimate_gbp ?? 0) >= 0}
            warning={(usePeriod ? periodFlow!.surplus_gbp : snapshot?.profit_estimate_gbp ?? 0) < 0}
            hint={
              usePeriod
                ? periodFlow!.coverage_note || "Stored transactions"
                : "Snapshot"
            }
          />
        </div>
      </section>

      {/* Position */}
      <section className="mt-8" aria-label="Business position">
        <h2 className="solar-section-title">Position</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Cash, debts, VAT, and debtors. Of-which business loans only — no personal loans here.
        </p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <MetricWithOfWhich
            ariaLabel="Business bank of which"
            items={
              overdraft > 0
                ? [{ label: "Of which business overdraft", value: overdraft }]
                : []
            }
          >
            <MetricTile
              label="Business bank"
              value={bankBalance}
              warning={overdraft > 0}
              hint="Positive current accounts"
            />
          </MetricWithOfWhich>
          <MetricWithOfWhich
            ariaLabel="Business debts of which"
            items={[
              {
                label: "Of which business loans",
                value: businessLoans > 0 ? businessLoans : null,
                hint: "Business-scope loans only — personal loans stay on Personal",
              },
            ]}
          >
            <MetricTile
              label="Business debts"
              value={businessDebts}
              warning={businessDebts > 0}
              hint="Company external debts — of which rows are subsets"
            />
          </MetricWithOfWhich>
          <MetricTile label="Business VAT pot" value={vatReserveGbp} hint="Cash in VAT pot" />
          <MetricTile label="Business corp tax reserve" value={snapshot?.corp_tax_reserve_gbp} />
          <MetricTile label="Business debtors" value={snapshot?.debtors_gbp} />
          <MetricTile
            label="Business director's loan"
            value={directorsLoan}
            positive={directorsLoan > 0}
            warning={directorsLoan < 0}
            hint={dlaHint}
          />
          <MetricTile label="Business cash to draw" value={snapshot?.cash_available_to_draw_gbp} />
        </div>
      </section>

      <div className="mt-8">
        <PlComparePanel scope="business" title="Business profit & loss compare" />
      </div>

      <section className="mt-8">
        <h2 className="solar-section-title">QuickFile statements</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Stored QuickFile reports (loaded after the page paints). Multi-month period chips above
          use stored business transactions for the historical window.
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
