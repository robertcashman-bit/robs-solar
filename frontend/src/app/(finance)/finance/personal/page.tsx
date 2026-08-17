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
import { isSandboxFinanceAccount } from "@/components/finance/finance-item-utils";
import { currentMonthKey, financeRoleForAccountBalance, formatGbp, parseRequiredNumber } from "@/lib/money";
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
    credit_limit_gbp: "",
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
    try {
      await apiClient.post("/finance/snapshots/personal", {
        snapshot_date: currentMonthKey(),
        monthly_income_gbp: parseRequiredNumber(snapshotForm.monthly_income_gbp, "Income"),
        monthly_spending_gbp: parseRequiredNumber(snapshotForm.monthly_spending_gbp, "Spending"),
        household_bills_gbp: parseRequiredNumber(snapshotForm.household_bills_gbp, "Household bills"),
        debt_repayments_gbp: parseRequiredNumber(snapshotForm.debt_repayments_gbp, "Debt repayments"),
      });
      setError(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save snapshot");
    }
  }

  async function addAccount(e: React.FormEvent) {
    e.preventDefault();
    if (!canWrite(user)) return;
    try {
      await apiClient.post("/finance/accounts", {
        scope: "personal",
        account_type: form.account_type,
        name: form.name,
        balance_gbp: parseRequiredNumber(form.balance_gbp, "Balance"),
        credit_limit_gbp:
          form.account_type === "credit_card" && form.credit_limit_gbp.trim()
            ? parseRequiredNumber(form.credit_limit_gbp, "Credit limit")
            : null,
      });
      setForm({ name: "", balance_gbp: "", account_type: "current", credit_limit_gbp: "" });
      setError(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add account");
    }
  }

  if (authLoading || !user) return <AuthLoadingShell />;

  const usableAccounts = accounts.filter((account) => !isSandboxFinanceAccount(account));
  const sandboxAccounts = accounts.filter((account) => isSandboxFinanceAccount(account));
  const totalBalance = usableAccounts.reduce((s, a) => s + a.balance_gbp, 0);

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
          historic={usableAccounts.some((a) => a.is_historic)}
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
          {usableAccounts.map((a) => (
            <li key={a.id} className="flex justify-between rounded-xl border border-[var(--border)] px-4 py-3 text-sm">
              <span>
                {a.name}{" "}
                <span className="text-[var(--muted)]">({a.account_type.replaceAll("_", " ")})</span>
                {a.credit_limit_gbp ? (
                  <span className="text-[var(--muted)]"> · limit {formatGbp(a.credit_limit_gbp)}</span>
                ) : a.account_type === "credit_card" ? (
                  <span className="text-[var(--muted)]"> · add a credit limit for available credit</span>
                ) : null}
                {a.is_historic ? <HistoricBadge /> : null}
              </span>
              <FinanceAmount
                value={a.balance_gbp}
                role={financeRoleForAccountBalance(a.account_type, a.balance_gbp)}
              />
            </li>
          ))}
          {usableAccounts.length === 0 ? (
            <li className="text-sm text-[var(--muted)]">No personal accounts yet.</li>
          ) : null}
          {sandboxAccounts.length > 0 ? (
            <li className="text-sm text-[var(--muted)]">
              {sandboxAccounts.length} sandbox account
              {sandboxAccounts.length === 1 ? "" : "s"} hidden from totals.
            </li>
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
            <option value="savings">Savings</option>
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
          {form.account_type === "credit_card" ? (
            <input
              className="solar-input"
              type="number"
              step="0.01"
              placeholder="Credit limit GBP"
              value={form.credit_limit_gbp}
              onChange={(e) => setForm({ ...form, credit_limit_gbp: e.target.value })}
            />
          ) : null}
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
