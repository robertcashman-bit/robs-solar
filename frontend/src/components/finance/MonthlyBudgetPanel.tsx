"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { z } from "zod";

import { apiClient } from "@/lib/api-client";
import { monthlyBudgetLineSchema, type MonthlyBudgetLine } from "@/lib/finance-schemas";
import { formatGbp, formatMonthLabel, parseGbp, parseRequiredAmount } from "@/lib/money";

type MonthlyBudgetPanelProps = {
  month: string;
  onMonthChange: (month: string) => void;
  writable: boolean;
  onStatus: (message: string) => void;
  onError: (message: string) => void;
};

export function MonthlyBudgetPanel({
  month,
  onMonthChange,
  writable,
  onStatus,
  onError,
}: MonthlyBudgetPanelProps) {
  const [scope, setScope] = useState<"personal" | "business">("personal");
  const [lines, setLines] = useState<MonthlyBudgetLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [category, setCategory] = useState("");
  const [budgeted, setBudgeted] = useState("");
  const [drafts, setDrafts] = useState<Record<number, { budgeted: string; actual: string }>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<unknown>(`/finance/budget?month=${month}&scope=${scope}`);
      const parsed = z.array(monthlyBudgetLineSchema).parse(data);
      setLines(parsed);
      setDrafts(
        Object.fromEntries(
          parsed.map((line) => [
            line.id,
            {
              budgeted: String(line.budgeted_gbp),
              actual: line.actual_recorded && line.actual_gbp != null ? String(line.actual_gbp) : "",
            },
          ]),
        ),
      );
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to load this month's budget");
    } finally {
      setLoading(false);
    }
  }, [month, scope, onError]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const totals = useMemo(() => {
    const budgetedTotal = lines.reduce((sum, line) => sum + line.budgeted_gbp, 0);
    const recorded = lines.filter((line) => line.actual_recorded && line.actual_gbp != null);
    const actualTotal = recorded.reduce((sum, line) => sum + (line.actual_gbp ?? 0), 0);
    return {
      budgeted: budgetedTotal,
      actual: actualTotal,
      remaining: recorded.length === lines.length && lines.length > 0 ? budgetedTotal - actualTotal : null,
      recordedCount: recorded.length,
    };
  }, [lines]);

  async function seedStarter() {
    if (!writable || saving) return;
    setSaving(true);
    try {
      await apiClient.post("/finance/budget/starter", {
        month,
        scope,
        from_active_plan: true,
      });
      onStatus("Starter categories added");
      await load();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Could not add starter categories");
    } finally {
      setSaving(false);
    }
  }

  async function addLine(event: React.FormEvent) {
    event.preventDefault();
    if (!writable || saving) return;
    setSaving(true);
    try {
      const amount = parseGbp(budgeted);
      if (!category.trim() || Number.isNaN(amount)) {
        throw new Error("Enter a category and a valid budget amount");
      }
      await apiClient.put("/finance/budget", {
        scope,
        month,
        category: category.trim(),
        budgeted_gbp: amount,
      });
      setCategory("");
      setBudgeted("");
      onStatus("Budget line saved");
      await load();
    } catch (err) {
      onError(err instanceof Error ? err.message : "The budget line could not be saved");
    } finally {
      setSaving(false);
    }
  }

  async function saveLine(line: MonthlyBudgetLine) {
    if (!writable || saving) return;
    setSaving(true);
    try {
      const draft = drafts[line.id] ?? { budgeted: "0", actual: "" };
      const budgetedAmount = parseRequiredAmount(draft.budgeted);
      if (budgetedAmount == null) {
        throw new Error("Enter a valid budgeted amount. Blank is not saved as £0.");
      }
      const payload: { budgeted_gbp: number; actual_gbp?: number } = {
        budgeted_gbp: budgetedAmount,
      };
      if (draft.actual.trim()) {
        const actualAmount = parseRequiredAmount(draft.actual);
        if (actualAmount == null) {
          throw new Error("Actual must be a number, or left blank if not recorded yet.");
        }
        payload.actual_gbp = actualAmount;
      }
      await apiClient.patch(`/finance/budget/${line.id}`, payload);
      onStatus(`Updated ${line.category}`);
      await load();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Could not update this line");
    } finally {
      setSaving(false);
    }
  }

  async function removeLine(line: MonthlyBudgetLine) {
    if (!writable || saving) return;
    setSaving(true);
    try {
      await apiClient.delete(`/finance/budget/${line.id}`);
      onStatus(`Removed ${line.category}`);
      await load();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Could not remove this line");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">{formatMonthLabel(month)}</h2>
        <label className="text-sm">
          <span className="sr-only">Month</span>
          <input
            type="month"
            className="solar-input text-sm"
            value={month}
            onChange={(event) => onMonthChange(event.target.value)}
          />
        </label>
      </div>
      <div className="flex gap-2">
        {(["personal", "business"] as const).map((item) => (
          <button
            key={item}
            type="button"
            className={`solar-btn-ghost capitalize ${scope === item ? "ring-2 ring-emerald-500" : ""}`}
            onClick={() => setScope(item)}
          >
            {item}
          </button>
        ))}
      </div>
      <p className="text-sm text-[var(--muted)]">
        Budgeted {formatGbp(totals.budgeted)} · Actual{" "}
        {totals.recordedCount ? formatGbp(totals.actual) : "not recorded yet"}
        {totals.remaining != null ? ` · Remaining ${formatGbp(totals.remaining)}` : ""}
      </p>
      {loading ? <p className="text-sm text-[var(--muted)]">Loading budget…</p> : null}
      {!loading && lines.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] px-4 py-6 text-sm text-[var(--muted)]">
          <p className="font-medium text-[var(--foreground)]">No budget lines yet</p>
          <p className="mt-1">
            Add categories for {scope} spending so you can track budgeted vs actual this month.
          </p>
          {writable ? (
            <button type="button" className="solar-btn-primary mt-4" disabled={saving} onClick={() => void seedStarter()}>
              {saving ? "Adding…" : "Add starter categories"}
            </button>
          ) : null}
        </div>
      ) : null}
      {lines.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-[var(--muted)]">
                <th className="py-2 pr-3">Category</th>
                <th className="py-2 pr-3">Budgeted</th>
                <th className="py-2 pr-3">Actual</th>
                <th className="py-2 pr-3">Remaining</th>
                <th className="py-2"> </th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line) => {
                const draft = drafts[line.id] ?? {
                  budgeted: String(line.budgeted_gbp),
                  actual: line.actual_recorded && line.actual_gbp != null ? String(line.actual_gbp) : "",
                };
                const remaining = line.actual_recorded && line.actual_gbp != null
                  ? line.budgeted_gbp - line.actual_gbp
                  : null;
                return (
                  <tr key={line.id} className="border-b border-[var(--border)]">
                    <td className="py-2 pr-3 font-medium">{line.category}</td>
                    <td className="py-2 pr-3">
                      {writable ? (
                        <input
                          className="solar-input w-28"
                          inputMode="decimal"
                          aria-label={`${line.category} budgeted`}
                          value={draft.budgeted}
                          onChange={(event) =>
                            setDrafts((current) => ({
                              ...current,
                              [line.id]: { ...draft, budgeted: event.target.value },
                            }))
                          }
                        />
                      ) : (
                        <span className="tabular-nums">{formatGbp(line.budgeted_gbp)}</span>
                      )}
                    </td>
                    <td className="py-2 pr-3">
                      {writable ? (
                        <input
                          className="solar-input w-28"
                          inputMode="decimal"
                          aria-label={`${line.category} actual`}
                          placeholder={line.actual_recorded ? undefined : "Missing"}
                          value={draft.actual}
                          onChange={(event) =>
                            setDrafts((current) => ({
                              ...current,
                              [line.id]: { ...draft, actual: event.target.value },
                            }))
                          }
                        />
                      ) : (
                        <span className="tabular-nums">{formatGbp(line.actual_gbp)}</span>
                      )}
                    </td>
                    <td className="py-2 pr-3 tabular-nums">
                      {remaining == null ? "—" : formatGbp(remaining)}
                    </td>
                    <td className="py-2">
                      {writable ? (
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            className="solar-btn-ghost text-xs"
                            disabled={saving}
                            onClick={() => void saveLine(line)}
                          >
                            Save
                          </button>
                          <button
                            type="button"
                            className="solar-btn-ghost text-xs"
                            disabled={saving}
                            onClick={() => void removeLine(line)}
                          >
                            Remove
                          </button>
                        </div>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
      {writable ? (
        <form onSubmit={(event) => void addLine(event)} className="flex flex-wrap gap-3">
          <label className="space-y-1 text-sm">
            <span>Category</span>
            <input
              className="solar-input"
              value={category}
              onChange={(event) => setCategory(event.target.value)}
              required
            />
          </label>
          <label className="space-y-1 text-sm">
            <span>Budget (£)</span>
            <input
              className="solar-input"
              inputMode="decimal"
              value={budgeted}
              onChange={(event) => setBudgeted(event.target.value)}
              required
            />
          </label>
          <button type="submit" className="solar-btn-primary self-end" disabled={saving}>
            {saving ? "Saving…" : "Add line"}
          </button>
        </form>
      ) : null}
    </section>
  );
}
