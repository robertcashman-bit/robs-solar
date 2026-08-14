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
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingValue, setEditingValue] = useState("");

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
    if (!canWrite(user) || saving) return;
    const amount = Number(budgeted);
    if (!Number.isFinite(amount)) {
      setError("Enter a valid budget amount. Blank or invalid values are not saved as zero.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await apiClient.put("/finance/budget", {
        scope,
        month,
        category,
        budgeted_gbp: amount,
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

  async function seedFromPrevious() {
    if (!canWrite(user) || saving) return;
    setSaving(true);
    setError(null);
    try {
      const seeded = await apiClient.post<MonthlyBudgetLine[]>(
        "/finance/budget/seed-from-previous",
        { month, scope },
      );
      const parsed = z.array(monthlyBudgetLineSchema).parse(seeded);
      await load();
      if (parsed.length === 0) {
        setError("No previous-month budget to copy for this scope.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to seed budget");
    } finally {
      setSaving(false);
    }
  }

  async function saveEditedLine(line: MonthlyBudgetLine) {
    if (!canWrite(user) || saving) return;
    const amount = Number(editingValue);
    if (!Number.isFinite(amount)) {
      setError("Enter a valid budget amount. Blank or invalid values are not saved as zero.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await apiClient.patch(`/finance/budget/${line.id}`, { budgeted_gbp: amount });
      setEditingId(null);
      setEditingValue("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update budget line");
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
      <div className="mt-4 flex flex-wrap gap-2">
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
        {canWrite(user) ? (
          <button
            type="button"
            className="solar-btn-secondary"
            disabled={saving || lines.length > 0}
            onClick={() => void seedFromPrevious()}
          >
            Fill from previous month
          </button>
        ) : null}
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
                description={`Add categories for ${scope} spending, or fill from the previous month. Actuals update from bank transactions.`}
              />
            </div>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <div className="grid grid-cols-4 gap-2 px-4 pb-2 text-xs uppercase tracking-wide text-[var(--muted)]">
                <span>Category</span>
                <span>Budgeted</span>
                <span>Actual</span>
                <span>Remaining</span>
              </div>
              <ul className="space-y-2">
                {lines.map((l) => (
                  <li
                    key={l.id}
                    className="grid grid-cols-4 gap-2 rounded-xl border border-[var(--border)] px-4 py-3 text-sm"
                  >
                    <span>{l.category}</span>
                    {canWrite(user) && editingId === l.id ? (
                      <form
                        className="flex gap-2"
                        onSubmit={(event) => {
                          event.preventDefault();
                          void saveEditedLine(l);
                        }}
                      >
                        <label className="sr-only" htmlFor={`budgeted-${l.id}`}>
                          Budgeted amount for {l.category}
                        </label>
                        <input
                          id={`budgeted-${l.id}`}
                          className="solar-input"
                          type="number"
                          step="0.01"
                          min="0"
                          value={editingValue}
                          onChange={(e) => setEditingValue(e.target.value)}
                          required
                        />
                        <button type="submit" className="solar-btn-primary" disabled={saving}>
                          Save
                        </button>
                        <button
                          type="button"
                          className="solar-btn-ghost"
                          onClick={() => {
                            setEditingId(null);
                            setEditingValue("");
                          }}
                        >
                          Cancel
                        </button>
                      </form>
                    ) : (
                      <button
                        type="button"
                        className="tabular-nums text-left underline-offset-2 hover:underline disabled:no-underline"
                        disabled={!canWrite(user)}
                        onClick={() => {
                          setEditingId(l.id);
                          setEditingValue(String(l.budgeted_gbp));
                        }}
                      >
                        {formatGbp(l.budgeted_gbp)}
                      </button>
                    )}
                    <span className="tabular-nums">{formatGbp(l.actual_gbp)}</span>
                    <span className="tabular-nums">{formatGbp(l.remaining_gbp)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {canWrite(user) ? (
            <form onSubmit={(e) => void addLine(e)} className="mt-6 flex flex-wrap gap-3">
              <label className="sr-only" htmlFor="budget-category">
                Category
              </label>
              <input
                id="budget-category"
                className="solar-input"
                placeholder="Category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                required
              />
              <label className="sr-only" htmlFor="budget-amount">
                Budget GBP
              </label>
              <input
                id="budget-amount"
                className="solar-input"
                type="number"
                step="0.01"
                min="0"
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
