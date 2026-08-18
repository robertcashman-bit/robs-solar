"use client";

import { useCallback, useState } from "react";
import { z } from "zod";

import { AccountManager } from "@/components/finance/AccountManager";
import { FinancePeriodScopeControl } from "@/components/finance/FinancePeriodScopeControl";
import { MetricTile } from "@/components/finance/MetricTile";
import { SavedFiguresBanner } from "@/components/finance/SavedFiguresBanner";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner, SuccessBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { apiClient } from "@/lib/api-client";
import { useRequireAuth } from "@/lib/use-require-auth";
import {
  financeAccountSchema,
  periodFlowSummarySchema,
  personalFinanceSnapshotSchema,
  type FinanceAccount,
  type PeriodFlowSummary,
  type PersonalFinanceSnapshot,
} from "@/lib/finance-schemas";
import { useFinanceBackgroundLiveRefresh } from "@/lib/use-finance-background-live-refresh";
import { useFinancePeriod } from "@/lib/use-finance-period";
import { useFinanceReload } from "@/lib/use-finance-reload";
import { currentMonthKey, isCurrentMonthSnapshot, parseGbp } from "@/lib/money";
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
  { value: "directors_loan", label: "Director's loan (company owes you)" },
];

export default function PersonalFinancePage() {
  const { user, gated, redirecting } = useRequireAuth();
  const [accounts, setAccounts] = useState<FinanceAccount[]>([]);
  const [snapshot, setSnapshot] = useState<PersonalFinanceSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [snapshotForm, setSnapshotForm] = useState({
    monthly_income_gbp: "",
    monthly_spending_gbp: "",
    household_bills_gbp: "",
    debt_repayments_gbp: "",
  });
  const periodState = useFinancePeriod({ fixedScope: "personal" });
  const [periodFlow, setPeriodFlow] = useState<PeriodFlowSummary | null>(null);

  const load = useCallback(async () => {
    try {
      const [accts, snaps, flow] = await Promise.all([
        apiClient.get<unknown>("/finance/accounts?scope=personal"),
        apiClient.get<unknown>("/finance/snapshots/personal"),
        apiClient.get<unknown>(
          `/finance/period-flow?period=${periodState.period}&scope=personal`,
        ),
      ]);
      const parsedFlow = periodFlowSummarySchema.safeParse(flow);
      setPeriodFlow(parsedFlow.success ? parsedFlow.data : null);
      setAccounts(z.array(financeAccountSchema).parse(accts));
      const parsed = z.array(personalFinanceSnapshotSchema).parse(snaps);
      const current = parsed.find((item) => isCurrentMonthSnapshot(item.snapshot_date)) ?? null;
      setSnapshot(current);
      if (current) {
        setSnapshotForm({
          monthly_income_gbp: String(current.monthly_income_gbp),
          monthly_spending_gbp: String(current.monthly_spending_gbp),
          household_bills_gbp: String(current.household_bills_gbp),
          debt_repayments_gbp: String(current.debt_repayments_gbp),
        });
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load personal finance");
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

  const cash = accounts.filter((a) => a.account_type === "current").reduce((s, a) => s + Math.max(a.balance_gbp, 0), 0);
  const pension = accounts
    .filter((a) => a.account_type === "pension")
    .reduce((s, a) => s + a.balance_gbp, 0);
  const companyOwes = accounts
    .filter((a) => a.account_type === "directors_loan")
    .reduce((s, a) => s + a.balance_gbp, 0);
  const property = accounts
    .filter((a) => a.account_type === "property")
    .reduce((s, a) => s + a.balance_gbp, 0);
  const mortgage = accounts
    .filter((a) => a.account_type === "mortgage")
    .reduce((s, a) => s + Math.abs(a.balance_gbp), 0);
  const assets = accounts
    .filter((a) => ["pension", "property", "other_asset"].includes(a.account_type))
    .reduce((s, a) => s + a.balance_gbp, 0);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Personal Finance"
        description="Current accounts, pension, property, and the director's loan the company owes you."
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
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <MetricTile label="Personal bank" value={cash} hint="Positive current accounts only" />
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
        <MetricTile
          label="Personal house mortgage (placeholder)"
          value={mortgage > 0 ? mortgage : null}
          warning={mortgage > 0}
          hint="Placeholder £175,000 for now."
        />
        <MetricTile
          label="Personal director's loan receivable"
          value={companyOwes}
          positive={companyOwes > 0}
          hint="Company owes you — cancels in combined net worth"
        />
        <MetricTile label="Personal assets" value={assets} hint="Pension, house share, other" />
        <MetricTile
          label={
            periodFlow && periodFlow.transaction_count > 0
              ? `Personal income (${periodFlow.label})`
              : "Personal monthly income"
          }
          value={
            periodFlow && periodFlow.transaction_count > 0
              ? periodFlow.income_gbp
              : snapshot?.monthly_income_gbp
          }
          hint={
            periodFlow && periodFlow.transaction_count > 0
              ? periodFlow.coverage_note || "Stored transactions"
              : "Snapshot"
          }
        />
        <MetricTile
          label={
            periodFlow && periodFlow.transaction_count > 0
              ? `Personal surplus (${periodFlow.label})`
              : "Personal monthly surplus"
          }
          value={
            periodFlow && periodFlow.transaction_count > 0
              ? periodFlow.surplus_gbp
              : snapshot?.surplus_deficit_gbp
          }
          positive={
            (periodFlow && periodFlow.transaction_count > 0
              ? periodFlow.surplus_gbp
              : snapshot?.surplus_deficit_gbp ?? 0) >= 0
          }
          hint={
            periodFlow && periodFlow.transaction_count > 0
              ? periodFlow.coverage_note || "Stored transactions"
              : "Snapshot"
          }
        />
      </div>
      <p className="mt-6 text-sm text-[var(--muted)]">
        The live app records your stated pension pot on first start. Edit the
        Pension account if that figure changes. A director&apos;s loan on this
        page is money the company owes you, not a debt.
      </p>
      <section className="mt-8">
        <h2 className="solar-section-title">Accounts</h2>
        <AccountManager
          scope="personal"
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
