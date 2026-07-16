"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { z } from "zod";

import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { EmptyState } from "@/components/shared/EmptyState";
import { PageHeader } from "@/components/shared/PageHeader";
import { PageLoading } from "@/components/shared/PageLoading";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { monthlyBudgetLineSchema, type MonthlyBudgetLine } from "@/lib/finance-schemas";
import { currentMonthKey, formatGbp, formatMonthLabel } from "@/lib/money";
import { canWrite } from "@/lib/permissions";

export default function BudgetPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [month, setMonth] = useState(currentMonthKey());
  const [scope, setScope] = useState<"personal" | "business">("personal");
  const [lines, setLines] = useState<MonthlyBudgetLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState("");
  const [budgeted, setBudgeted] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<unknown>(`/finance/budget?month=${month}&scope=${scope}`);
      setLines(z.array(monthlyBudgetLineSchema).parse(data));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load budget");
    } finally {
      setLoading(false);
    }
  }, [month, scope]);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [user, load]);

  async function addLine(e: React.FormEvent) {
    e.preventDefault();
    if (!canWrite(user)) return;
    setSaving(true);
    setError(null);
    try {
      await apiClient.put("/finance/budget", {
        scope,
        month,
        category,
        budgeted_gbp: Number(budgeted),
        actual_gbp: 0,
      });
      setCategory("");
      setBudgeted("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add budget line");
    } finally {
      setSaving(false);
    }
  }

  if (authLoading || !user) return <AuthLoadingShell />;

  const totalBudget = lines.reduce((s, l) => s + l.budgeted_gbp, 0);
  const totalActual = lines.reduce((s, l) => s + l.actual_gbp, 0);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Budget"
        description={`Household and business budgets for ${formatMonthLabel(month)}.`}
        actions={
          <input
            type="month"
            className="solar-input text-sm"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
          />
        }
      />
      {error ? (
        <div className="mt-4">
          <ErrorBanner message={error} />
        </div>
      ) : null}
      <div className="mt-4 flex gap-2">
        {(["personal", "business"] as const).map((s) => (
          <button
            key={s}
            type="button"
            className={`solar-btn-ghost capitalize ${scope === s ? "ring-2 ring-emerald-500" : ""}`}
            onClick={() => setScope(s)}
          >
            {s}
          </button>
        ))}
      </div>
      {loading ? (
        <div className="mt-6">
          <PageLoading label="Loading budget" rows={2} />
        </div>
      ) : (
        <>
          <p className="mt-4 text-sm text-[var(--muted)]">
            Budgeted {formatGbp(totalBudget)} · Actual {formatGbp(totalActual)} · Remaining{" "}
            {formatGbp(totalBudget - totalActual)}
          </p>
          {lines.length === 0 ? (
            <div className="mt-6">
              <EmptyState
                title="No budget lines yet"
                description={`Add categories for ${scope} spending so you can track budgeted vs actual this month.`}
              />
            </div>
          ) : (
            <ul className="mt-4 space-y-2">
              {lines.map((l) => (
                <li
                  key={l.id}
                  className="grid grid-cols-4 gap-2 rounded-xl border border-[var(--border)] px-4 py-3 text-sm"
                >
                  <span>{l.category}</span>
                  <span className="tabular-nums">{formatGbp(l.budgeted_gbp)}</span>
                  <span className="tabular-nums">{formatGbp(l.actual_gbp)}</span>
                  <span className="tabular-nums">{formatGbp(l.remaining_gbp)}</span>
                </li>
              ))}
            </ul>
          )}
          {canWrite(user) ? (
            <form onSubmit={(e) => void addLine(e)} className="mt-6 flex flex-wrap gap-3">
              <input
                className="solar-input"
                placeholder="Category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                required
              />
              <input
                className="solar-input"
                type="number"
                placeholder="Budget GBP"
                value={budgeted}
                onChange={(e) => setBudgeted(e.target.value)}
                required
              />
              <button type="submit" className="solar-btn-primary" disabled={saving}>
                {saving ? "Saving…" : "Add line"}
              </button>
            </form>
          ) : null}
        </>
      )}
    </AppShell>
  );
}
