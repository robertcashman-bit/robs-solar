"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { z } from "zod";

import { MetricTile } from "@/components/finance/MetricTile";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import {
  businessFinanceSnapshotSchema,
  financeAccountSchema,
  type BusinessFinanceSnapshot,
  type FinanceAccount,
} from "@/lib/finance-schemas";
import { currentMonthKey, formatGbp } from "@/lib/money";
import { canWrite } from "@/lib/permissions";

export default function BusinessFinancePage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [accounts, setAccounts] = useState<FinanceAccount[]>([]);
  const [snapshot, setSnapshot] = useState<BusinessFinanceSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    balance_gbp: "",
    account_type: "current",
  });
  const [snapshotForm, setSnapshotForm] = useState({
    turnover_gbp: "",
    expenses_gbp: "",
    vat_reserve_gbp: "",
    corp_tax_reserve_gbp: "",
    debtors_gbp: "",
    creditors_gbp: "",
  });

  const load = useCallback(async () => {
    try {
      const [accts, snaps] = await Promise.all([
        apiClient.get<unknown>("/finance/accounts?scope=business"),
        apiClient.get<unknown>("/finance/snapshots/business"),
      ]);
      setAccounts(z.array(financeAccountSchema).parse(accts));
      const parsed = z.array(businessFinanceSnapshotSchema).parse(snaps);
      setSnapshot(parsed[0] ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load business finance");
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

  async function addAccount(e: React.FormEvent) {
    e.preventDefault();
    if (!canWrite(user)) return;
    await apiClient.post("/finance/accounts", {
      scope: "business",
      account_type: form.account_type,
      name: form.name,
      balance_gbp: Number(form.balance_gbp),
    });
    setForm({ name: "", balance_gbp: "", account_type: "current" });
    await load();
  }

  async function saveSnapshot(e: React.FormEvent) {
    e.preventDefault();
    if (!canWrite(user)) return;
    await apiClient.post("/finance/snapshots/business", {
      snapshot_date: currentMonthKey(),
      turnover_gbp: Number(snapshotForm.turnover_gbp),
      expenses_gbp: Number(snapshotForm.expenses_gbp),
      vat_reserve_gbp: Number(snapshotForm.vat_reserve_gbp),
      corp_tax_reserve_gbp: Number(snapshotForm.corp_tax_reserve_gbp),
      debtors_gbp: Number(snapshotForm.debtors_gbp),
      creditors_gbp: Number(snapshotForm.creditors_gbp),
    });
    await load();
  }

  if (authLoading || !user) return <AuthLoadingShell />;

  const bankBalance = accounts
    .filter((a) => a.account_type === "current")
    .reduce((s, a) => s + a.balance_gbp, 0);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Business Finance"
        description="Turnover, expenses, VAT and corporation tax reserves, debtors, creditors, and cash to draw."
      />
      {error ? <div className="mt-4"><ErrorBanner message={error} /></div> : null}
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricTile label="Business bank" value={bankBalance} />
        <MetricTile label="Turnover (month)" value={snapshot?.turnover_gbp} />
        <MetricTile label="Expenses (month)" value={snapshot?.expenses_gbp} />
        <MetricTile label="Profit estimate" value={snapshot?.profit_estimate_gbp} positive />
        <MetricTile label="VAT reserve" value={snapshot?.vat_reserve_gbp} />
        <MetricTile label="Corp tax reserve" value={snapshot?.corp_tax_reserve_gbp} />
        <MetricTile label="Debtors" value={snapshot?.debtors_gbp} />
        <MetricTile label="Cash to draw" value={snapshot?.cash_available_to_draw_gbp} />
      </div>
      <section className="mt-8">
        <h2 className="solar-section-title">Business accounts</h2>
        <ul className="mt-3 space-y-2">
          {accounts.map((a) => (
            <li key={a.id} className="flex justify-between rounded-xl border border-[var(--border)] px-4 py-3 text-sm">
              <span>{a.name}</span>
              <span className="font-semibold tabular-nums">{formatGbp(a.balance_gbp)}</span>
            </li>
          ))}
          {accounts.length === 0 ? (
            <li className="text-sm text-[var(--muted)]">No business accounts yet.</li>
          ) : null}
        </ul>
      </section>
      {canWrite(user) ? (
        <>
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
              <option value="vat_reserve">VAT reserve</option>
              <option value="corp_tax_reserve">Corp tax reserve</option>
              <option value="capital_on_tap">Capital on Tap</option>
              <option value="debtors">Debtors</option>
              <option value="creditors">Creditors</option>
              <option value="directors_loan">Director&apos;s loan</option>
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
          <section className="mt-8">
            <h2 className="solar-section-title">Monthly snapshot ({currentMonthKey()})</h2>
            <form
              onSubmit={(e) => void saveSnapshot(e)}
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
                  type="number"
                  step="0.01"
                  placeholder={label}
                  value={snapshotForm[key]}
                  onChange={(e) => setSnapshotForm({ ...snapshotForm, [key]: e.target.value })}
                  required
                />
              ))}
              <button type="submit" className="solar-btn-primary sm:col-span-2">
                Save snapshot
              </button>
            </form>
          </section>
        </>
      ) : null}
    </AppShell>
  );
}
