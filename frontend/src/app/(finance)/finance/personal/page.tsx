"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { z } from "zod";

import { FinanceAmount } from "@/components/finance/FinanceAmount";
import { FinanceSignLegend } from "@/components/finance/FinanceSignLegend";
import { MetricTile } from "@/components/finance/MetricTile";
import { HistoricBadge } from "@/components/finance/HistoricBadge";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import {
  financeAccountSchema,
  personalFinanceSnapshotSchema,
  type FinanceAccount,
  type PersonalFinanceSnapshot,
} from "@/lib/finance-schemas";
import { currentMonthKey, financeRoleForAccountBalance } from "@/lib/money";
import { canWrite } from "@/lib/permissions";

export default function PersonalFinancePage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [accounts, setAccounts] = useState<FinanceAccount[]>([]);
  const [snapshot, setSnapshot] = useState<PersonalFinanceSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    balance_gbp: "",
    account_type: "current",
  });
  const [snapshotForm, setSnapshotForm] = useState({
    monthly_income_gbp: "",
    monthly_spending_gbp: "",
    household_bills_gbp: "",
    debt_repayments_gbp: "",
  });

  const load = useCallback(async () => {
    try {
      const [accts, snaps] = await Promise.all([
        apiClient.get<unknown>("/finance/accounts?scope=personal"),
        apiClient.get<unknown>("/finance/snapshots/personal"),
      ]);
      setAccounts(z.array(financeAccountSchema).parse(accts));
      const parsed = z.array(personalFinanceSnapshotSchema).parse(snaps);
      setSnapshot(parsed[0] ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load personal finance");
    }
  }, []);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [user, load]);

  async function saveSnapshot(e: React.FormEvent) {
    e.preventDefault();
    if (!canWrite(user)) return;
    await apiClient.post("/finance/snapshots/personal", {
      snapshot_date: currentMonthKey(),
      monthly_income_gbp: Number(snapshotForm.monthly_income_gbp),
      monthly_spending_gbp: Number(snapshotForm.monthly_spending_gbp),
      household_bills_gbp: Number(snapshotForm.household_bills_gbp),
      debt_repayments_gbp: Number(snapshotForm.debt_repayments_gbp),
    });
    await load();
  }

  async function addAccount(e: React.FormEvent) {
    e.preventDefault();
    if (!canWrite(user)) return;
    await apiClient.post("/finance/accounts", {
      scope: "personal",
      account_type: form.account_type,
      name: form.name,
      balance_gbp: Number(form.balance_gbp),
    });
    setForm({ name: "", balance_gbp: "", account_type: "current" });
    await load();
  }

  if (authLoading || !user) return <AuthLoadingShell />;

  const totalBalance = accounts.reduce((s, a) => s + a.balance_gbp, 0);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Personal Finance"
        description="Current accounts, credit cards, loans, mortgage, pension, and household cash flow."
      />
      <p className="mt-2 text-sm">
        <Link href="/finance/connect" className="underline text-[var(--muted)]">
          Connect or refresh personal bank logins →
        </Link>
      </p>
      {error ? <div className="mt-4"><ErrorBanner message={error} /></div> : null}
      <div className="mt-4">
        <FinanceSignLegend />
      </div>
      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <MetricTile
          label="Total personal balance"
          value={totalBalance}
          amountRole="signed"
          historic={accounts.some((a) => a.is_historic)}
        />
        <MetricTile
          label="Monthly income"
          value={snapshot?.monthly_income_gbp}
          amountRole="inflow"
          historic={Boolean(snapshot)}
        />
        <MetricTile
          label="Monthly surplus"
          value={snapshot?.surplus_deficit_gbp}
          amountRole="signed"
          historic={Boolean(snapshot)}
        />
      </div>
      <section className="mt-8">
        <h2 className="solar-section-title">Accounts</h2>
        <ul className="mt-3 space-y-2">
          {accounts.map((a) => (
            <li key={a.id} className="flex justify-between rounded-xl border border-[var(--border)] px-4 py-3 text-sm">
              <span>
                {a.name}{" "}
                <span className="text-[var(--muted)]">({a.account_type.replaceAll("_", " ")})</span>
                {a.is_historic ? <HistoricBadge /> : null}
              </span>
              <FinanceAmount
                value={a.balance_gbp}
                role={financeRoleForAccountBalance(a.account_type, a.balance_gbp)}
              />
            </li>
          ))}
          {accounts.length === 0 ? (
            <li className="text-sm text-[var(--muted)]">No personal accounts yet.</li>
          ) : null}
        </ul>
      </section>
      {canWrite(user) ? (
        <form
          onSubmit={(e) => void addAccount(e)}
          className="mt-6 grid gap-3 rounded-2xl border border-[var(--border)] p-4 sm:grid-cols-4"
        >
          <input
            className="solar-input"
            placeholder="Account name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />
          <select
            className="solar-input"
            value={form.account_type}
            onChange={(e) => setForm({ ...form, account_type: e.target.value })}
          >
            <option value="current">Current</option>
            <option value="credit_card">Credit card</option>
            <option value="loan">Loan</option>
            <option value="mortgage">Mortgage</option>
            <option value="property">Property</option>
            <option value="pension">Pension</option>
          </select>
          <input
            className="solar-input"
            type="number"
            step="0.01"
            placeholder="Balance GBP"
            value={form.balance_gbp}
            onChange={(e) => setForm({ ...form, balance_gbp: e.target.value })}
            required
          />
          <button type="submit" className="solar-btn-primary">
            Add account
          </button>
        </form>
      ) : null}
      {canWrite(user) ? (
        <section className="mt-8">
          <h2 className="solar-section-title">Monthly snapshot ({currentMonthKey()})</h2>
          <form
            onSubmit={(e) => void saveSnapshot(e)}
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
                type="number"
                step="0.01"
                placeholder={label}
                value={snapshotForm[key]}
                onChange={(e) => setSnapshotForm({ ...snapshotForm, [key]: e.target.value })}
                required
              />
            ))}
            <button type="submit" className="solar-btn-primary">
              Save snapshot
            </button>
          </form>
        </section>
      ) : null}
    </AppShell>
  );
}
