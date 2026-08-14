"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { EmptyState } from "@/components/shared/EmptyState";
import { calculateBudgetTotals, parseBudgetAmount, type BudgetView } from "@/lib/budget-engine";
import type {
  BudgetMissingInput,
  BudgetPlanItem,
  BudgetPlanSummary,
  BudgetSuggestion,
  BudgetSuggestions,
} from "@/lib/finance-schemas";
import { formatGbp } from "@/lib/money";

const STRATEGY_COPY: Record<string, { title: string; purpose: string }> = {
  stabilise: {
    title: "Stabilise",
    purpose: "Prioritise liquidity and cover required payments first.",
  },
  balanced: {
    title: "Balanced",
    purpose: "Cover commitments, keep a buffer, and reduce high-cost debt steadily.",
  },
  debt_attack: {
    title: "Debt Attack",
    purpose: "Direct more available surplus toward expensive debt after required payments.",
  },
  custom: {
    title: "Custom",
    purpose: "Start from a suggestion or a blank allocation and edit every figure.",
  },
};

const KIND_LABELS: Record<string, string> = {
  income: "Income",
  essential: "Essential / commitments",
  debt_minimum: "Debt minimums",
  debt_overpayment: "Additional debt repayment",
  tax_provision: "Tax provision",
  buffer: "Buffer / savings contribution",
  discretionary: "Discretionary",
  other: "Other",
};

const KIND_ORDER = [
  "income",
  "essential",
  "debt_minimum",
  "debt_overpayment",
  "tax_provision",
  "buffer",
  "discretionary",
  "other",
];

type WorkingItem = BudgetPlanItem & { draft: string };

type BudgetPlanViewProps = {
  suggestions: BudgetSuggestions;
  initialPlan?: { id: number; name: string; strategy: BudgetSuggestion["strategy"]; items: BudgetPlanItem[] } | null;
  canWrite: boolean;
  saving: boolean;
  onSave: (payload: {
    name: string;
    strategy: "stabilise" | "balanced" | "debt_attack" | "custom";
    items: BudgetPlanItem[];
    fingerprint: string;
    activate: boolean;
    planId: number | null;
  }) => Promise<void>;
  onActivate: (planId: number) => Promise<void>;
  onDeactivate: (planId: number) => Promise<void>;
  onDuplicate: (planId: number) => Promise<void>;
  onReset: (planId: number) => Promise<void>;
  onRefresh: (planId: number) => Promise<void>;
  onDelete: (planId: number) => Promise<void>;
  onLoadPlan: (planId: number) => Promise<BudgetPlanItem[] | null>;
};

function toWorking(items: BudgetPlanItem[]): WorkingItem[] {
  return items.map((item) => ({
    ...item,
    draft: item.amount_gbp == null ? "" : String(item.amount_gbp),
  }));
}

function fromWorking(items: WorkingItem[]): BudgetPlanItem[] {
  return items.map((item) => {
    const { draft, ...rest } = item;
    void draft;
    return rest;
  });
}

function formatAmountOrMissing(value: number | null | undefined, missing: boolean): string {
  if (missing || value == null) {
    return "Missing / needs input";
  }
  return formatGbp(value);
}

export function BudgetPlanView({
  suggestions,
  initialPlan = null,
  canWrite,
  saving,
  onSave,
  onActivate,
  onDeactivate,
  onDuplicate,
  onReset,
  onRefresh,
  onDelete,
  onLoadPlan,
}: BudgetPlanViewProps) {
  const [started, setStarted] = useState(suggestions.saved_plans.length > 0 || Boolean(initialPlan));
  const [strategy, setStrategy] = useState<"stabilise" | "balanced" | "debt_attack" | "custom">(
    initialPlan?.strategy ?? suggestions.recommended_strategy,
  );
  const initial = suggestions.suggestions.find((s) => s.strategy === suggestions.recommended_strategy);
  const [items, setItems] = useState<WorkingItem[]>(
    toWorking(initialPlan?.items ?? initial?.items ?? []),
  );
  const [name, setName] = useState(initialPlan?.name ?? initial?.name ?? "Balanced");
  const [planId, setPlanId] = useState<number | null>(initialPlan?.id ?? suggestions.active_plan_id ?? null);
  const [view, setView] = useState<BudgetView>("consolidated");
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [newCategory, setNewCategory] = useState("");
  const [newKind, setNewKind] = useState<BudgetPlanItem["kind"]>("other");
  const [newScope, setNewScope] = useState<"personal" | "business">("personal");
  const [newAmount, setNewAmount] = useState("");

  const totals = useMemo(() => calculateBudgetTotals(items, view), [items, view]);
  const comparison = useMemo(() => {
    const rows: {
      key: string;
      name: string;
      totals: {
        income_gbp: number;
        committed_gbp: number;
        debt_minimum_gbp: number;
        debt_overpayment_gbp: number;
        buffer_gbp: number;
        discretionary_gbp: number;
        surplus_gbp: number | null;
      };
    }[] = suggestions.suggestions.map((suggestion) => ({
      key: suggestion.strategy,
      name: suggestion.name,
      totals: suggestion.totals_consolidated,
    }));
    rows.push({
      key: "working",
      name: name || "Current edit",
      totals: calculateBudgetTotals(items, "consolidated"),
    });
    return rows;
  }, [suggestions.suggestions, name, items]);

  const visibleItems = items.filter((item) =>
    view === "consolidated" ? true : item.scope === view,
  );
  const grouped = KIND_ORDER.map((kind) => ({
    kind,
    items: visibleItems.filter((item) => item.kind === kind),
  })).filter((group) => group.items.length > 0);

  const missing: BudgetMissingInput[] = suggestions.missing;
  const activeId = suggestions.active_plan_id ?? null;
  const currentSaved = suggestions.saved_plans.find((plan) => plan.id === planId);

  function applySuggestion(next: BudgetSuggestion) {
    setStrategy(next.strategy);
    setItems(toWorking(next.items));
    setName(next.name);
    setPlanId(null);
    setError(null);
  }

  function updateDraft(key: string, draft: string) {
    setItems((current) =>
      current.map((item) => {
        if (item.key !== key) return item;
        try {
          const parsed = parseBudgetAmount(draft);
          return {
            ...item,
            draft,
            amount_gbp: parsed,
            is_missing: parsed == null,
            is_user_override: true,
            source: "user_override",
            source_label: "User override",
          };
        } catch {
          return { ...item, draft };
        }
      }),
    );
  }

  function renameItem(key: string, category: string) {
    setItems((current) =>
      current.map((item) => (item.key === key ? { ...item, category } : item)),
    );
  }

  function toggleTransfer(key: string) {
    setItems((current) =>
      current.map((item) =>
        item.key === key ? { ...item, is_transfer: !item.is_transfer } : item,
      ),
    );
  }

  function removeItem(key: string) {
    setItems((current) => current.filter((item) => item.key !== key));
  }

  function addCategory(event: React.FormEvent) {
    event.preventDefault();
    const category = newCategory.trim();
    if (!category) {
      setError("Category name is required.");
      return;
    }
    let amount: number | null;
    try {
      amount = parseBudgetAmount(newAmount);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Enter a valid amount.");
      return;
    }
    const key = `${newScope}:${newKind}:user:${Date.now()}:${category.toLowerCase()}`;
    setItems((current) => [
      ...current,
      {
        key,
        scope: newScope,
        kind: newKind,
        category,
        amount_gbp: amount,
        source: "user_entered",
        source_label: "User entered",
        is_generated: false,
        is_user_override: false,
        is_transfer: false,
        is_missing: amount == null,
        notes: "",
        draft: newAmount,
      },
    ]);
    setNewCategory("");
    setNewAmount("");
    setError(null);
  }

  async function handleSave(activate: boolean) {
    if (!canWrite) return;
    for (const item of items) {
      try {
        parseBudgetAmount(item.draft);
      } catch (err) {
        setError(err instanceof Error ? err.message : `Invalid amount for ${item.category}`);
        return;
      }
    }
    setError(null);
    await onSave({
      name: name.trim() || "Custom budget",
      strategy: planId ? "custom" : strategy,
      items: fromWorking(items),
      fingerprint: suggestions.fingerprint,
      activate,
      planId,
    });
  }

  async function handleSelectSaved(plan: BudgetPlanSummary) {
    const loaded = await onLoadPlan(plan.id);
    if (!loaded) return;
    setPlanId(plan.id);
    setName(plan.name);
    setStrategy(plan.strategy);
    setItems(toWorking(loaded));
  }

  if (!started) {
    return (
      <EmptyState
        title="Create your first budget"
        description="Rob's Finance will analyse the income, debts, tax reserves, and commitments already on file, then offer Stabilise, Balanced, and Debt Attack plans. Missing figures stay missing until you enter them."
        action={
          <button
            type="button"
            className="solar-btn-primary"
            onClick={() => setStarted(true)}
          >
            Create your first budget
          </button>
        }
      />
    );
  }

  const surplus = totals.surplus_gbp;
  const equationResult =
    !totals.income_complete
      ? totals.incomplete_reason
      : surplus != null && surplus < 0
        ? `Projected monthly shortfall: ${formatGbp(Math.abs(surplus))}`
        : `Projected monthly surplus: ${formatGbp(surplus ?? 0)}`;

  return (
    <div className="space-y-8">
      {error ? (
        <p role="alert" className="rounded-xl border border-red-300/50 bg-red-50/90 px-4 py-3 text-sm text-red-800">
          {error}
        </p>
      ) : null}

      {currentSaved?.source_stale ? (
        <div className="rounded-xl border border-amber-400/40 bg-amber-500/10 px-4 py-3 text-sm">
          <p className="font-medium">Underlying financial data has changed since this budget was created.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" className="solar-btn-secondary" disabled={saving || !planId} onClick={() => planId && void onRefresh(planId)}>
              Refresh suggested figures
            </button>
            <span className="self-center text-[var(--muted)]">or keep your budget as it is.</span>
          </div>
        </div>
      ) : null}

      <section aria-label="Budget overview" className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Budget overview</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">
              {name}
              {planId && activeId === planId ? (
                <span className="ml-2 rounded-full bg-emerald-600 px-2 py-0.5 text-xs font-semibold text-white">
                  Active
                </span>
              ) : planId ? (
                <span className="ml-2 rounded-full border border-[var(--border)] px-2 py-0.5 text-xs">Saved</span>
              ) : (
                <span className="ml-2 rounded-full border border-[var(--border)] px-2 py-0.5 text-xs">Suggested</span>
              )}
              {totals.has_missing_inputs ? (
                <span className="ml-2 rounded-full border border-amber-400 px-2 py-0.5 text-xs">Has missing inputs</span>
              ) : null}
              {totals.is_deficit ? (
                <span className="ml-2 rounded-full bg-red-600 px-2 py-0.5 text-xs font-semibold text-white">
                  Deficit
                </span>
              ) : null}
            </p>
          </div>
          <label className="text-sm">
            <span className="sr-only">Budget name</span>
            <input
              className="solar-input"
              value={name}
              onChange={(event) => setName(event.target.value)}
              disabled={!canWrite}
              aria-label="Budget name"
            />
          </label>
        </div>

        <div className="mt-4 flex flex-wrap gap-2" role="tablist" aria-label="Budget view">
          {(["personal", "business", "consolidated"] as const).map((option) => (
            <button
              key={option}
              type="button"
              role="tab"
              aria-selected={view === option}
              className={`solar-btn-ghost capitalize ${view === option ? "ring-2 ring-emerald-500" : ""}`}
              onClick={() => setView(option)}
            >
              {option} budget
            </button>
          ))}
        </div>

        <dl className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Metric label="Monthly income" value={formatGbp(totals.income_gbp)} />
          <Metric label="Committed expenditure" value={formatGbp(totals.committed_gbp)} />
          <Metric label="Debt minimums" value={formatGbp(totals.debt_minimum_gbp)} />
          <Metric label="Debt overpayment" value={formatGbp(totals.debt_overpayment_gbp)} />
          <Metric label="Tax provision" value={formatGbp(totals.tax_provision_gbp)} />
          <Metric label="Savings / buffer" value={formatGbp(totals.buffer_gbp)} />
          <Metric label="Discretionary" value={formatGbp(totals.discretionary_gbp)} />
          <Metric
            label="Projected surplus / deficit"
            value={equationResult}
            tone={surplus == null ? "muted" : surplus < 0 ? "bad" : "good"}
          />
        </dl>

        <p className="mt-4 rounded-xl border border-[var(--border)] px-4 py-3 text-sm">
          <span className="font-medium">Monthly income</span> {formatGbp(totals.income_gbp)} minus{" "}
          <span className="font-medium">monthly allocations</span> {formatGbp(totals.allocated_gbp)} equals{" "}
          <span className={surplus != null && surplus < 0 ? "font-semibold text-red-600 dark:text-red-400" : "font-semibold"}>
            {equationResult}
          </span>
        </p>
        {suggestions.cash.savings_accounts_found && suggestions.cash.savings_balance_gbp != null ? (
          <p className="mt-2 text-sm text-[var(--muted)]">
            Existing savings balance on file: {formatGbp(suggestions.cash.savings_balance_gbp)} (cash held, not this month&apos;s contribution).
          </p>
        ) : (
          <p className="mt-2 text-sm text-[var(--muted)]">
            No savings account on file — existing cash buffer is unknown, not assumed to be zero.
          </p>
        )}
      </section>

      {missing.length > 0 ? (
        <section aria-label="Needs attention" className="rounded-2xl border border-amber-400/40 bg-amber-500/10 p-4">
          <h2 className="text-lg font-semibold">Needs attention</h2>
          <ul className="mt-3 space-y-2 text-sm">
            {missing.map((item) => (
              <li key={`${item.code}-${item.source_record_id ?? item.message}`}>
                {item.record_href ? (
                  <Link href={item.record_href} className="underline underline-offset-2">
                    {item.message}
                  </Link>
                ) : (
                  item.message
                )}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section aria-label="Budget options">
        <h2 className="text-lg font-semibold">Budget options</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Each option is calculated from records already in Rob&apos;s Finance. Nothing is invented to make a plan balance.
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-2" role="radiogroup" aria-label="Suggested budget approach">
          {suggestions.suggestions.map((option) => {
            const selected = strategy === option.strategy && planId == null;
            const copy = STRATEGY_COPY[option.strategy];
            return (
              <button
                key={option.strategy}
                type="button"
                role="radio"
                aria-checked={selected}
                className={`rounded-2xl border px-4 py-4 text-left ${
                  selected ? "border-emerald-500 ring-2 ring-emerald-500" : "border-[var(--border)]"
                }`}
                onClick={() => applySuggestion(option)}
                disabled={!canWrite}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold">{copy.title}</span>
                  {option.recommended ? (
                    <span className="rounded-full bg-emerald-600 px-2 py-0.5 text-xs font-semibold text-white">
                      Suggested
                    </span>
                  ) : null}
                  {selected ? (
                    <span className="text-xs font-medium text-emerald-700 dark:text-emerald-300">Selected</span>
                  ) : null}
                </div>
                <p className="mt-1 text-sm text-[var(--muted)]">{copy.purpose}</p>
                <p className="mt-3 text-sm">
                  Income {formatGbp(option.totals_consolidated.income_gbp)} · Allocated{" "}
                  {formatGbp(option.totals_consolidated.allocated_gbp)}
                </p>
              </button>
            );
          })}
        </div>
      </section>

      <section aria-label="Budget categories">
        <h2 className="text-lg font-semibold">Budget categories</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Every suggested figure can be changed. Blank means missing — it is not saved as zero.
        </p>
        <div className="mt-4 space-y-6">
          {grouped.map((group) => (
            <div key={group.kind}>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
                {KIND_LABELS[group.kind] ?? group.kind}
              </h3>
              <ul className="mt-2 space-y-2">
                {group.items.map((item) => (
                  <li
                    key={item.key}
                    className="rounded-xl border border-[var(--border)] px-3 py-3 sm:px-4"
                  >
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
                      <label className="min-w-0 flex-1 text-sm">
                        <span className="sr-only">Category name</span>
                        <input
                          className="solar-input w-full"
                          value={item.category}
                          onChange={(event) => renameItem(item.key, event.target.value)}
                          disabled={!canWrite}
                          aria-label={`Category name for ${item.category}`}
                        />
                      </label>
                      <label className="w-full lg:w-40 text-sm">
                        <span className="sr-only">Amount for {item.category}</span>
                        <input
                          className="solar-input w-full"
                          inputMode="decimal"
                          value={item.draft}
                          placeholder="Missing"
                          onChange={(event) => updateDraft(item.key, event.target.value)}
                          disabled={!canWrite}
                          aria-label={`Monthly amount for ${item.category}`}
                          aria-invalid={item.draft !== "" && Number.isNaN(Number(item.draft.replace(/[£$,]/g, "")))}
                        />
                      </label>
                      <p className="text-sm tabular-nums text-[var(--muted)] lg:w-36">
                        {formatAmountOrMissing(item.amount_gbp, item.is_missing)}
                      </p>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-[var(--muted)]">
                      <span>{item.source_label || item.source}</span>
                      <span className="capitalize">{item.scope}</span>
                      {item.is_transfer ? <span>Transfer (excluded from consolidated)</span> : null}
                      {item.record_href ? (
                        <Link href={item.record_href} className="underline">
                          Open source record
                        </Link>
                      ) : null}
                      {canWrite ? (
                        <button type="button" className="underline" onClick={() => toggleTransfer(item.key)}>
                          {item.is_transfer ? "Treat as external" : "Mark as transfer"}
                        </button>
                      ) : null}
                      {canWrite && (item.source === "user_entered" || item.source === "user_override") ? (
                        <button type="button" className="underline" onClick={() => removeItem(item.key)}>
                          Remove
                        </button>
                      ) : null}
                    </div>
                    {item.notes ? <p className="mt-1 text-xs text-[var(--muted)]">{item.notes}</p> : null}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {canWrite ? (
          <form onSubmit={addCategory} className="mt-6 grid gap-3 rounded-2xl border border-[var(--border)] p-4 sm:grid-cols-2 lg:grid-cols-5">
            <label className="text-sm">
              <span className="mb-1 block text-xs uppercase tracking-wide text-[var(--muted)]">Category</span>
              <input
                id="new-budget-category"
                className="solar-input w-full"
                value={newCategory}
                onChange={(event) => setNewCategory(event.target.value)}
                required
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-xs uppercase tracking-wide text-[var(--muted)]">Amount</span>
              <input
                id="new-budget-amount"
                className="solar-input w-full"
                inputMode="decimal"
                value={newAmount}
                onChange={(event) => setNewAmount(event.target.value)}
                placeholder="Leave blank if unknown"
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-xs uppercase tracking-wide text-[var(--muted)]">Kind</span>
              <select
                className="solar-input w-full"
                value={newKind}
                onChange={(event) => setNewKind(event.target.value as BudgetPlanItem["kind"])}
              >
                {KIND_ORDER.map((kind) => (
                  <option key={kind} value={kind}>
                    {KIND_LABELS[kind]}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-xs uppercase tracking-wide text-[var(--muted)]">Scope</span>
              <select
                className="solar-input w-full"
                value={newScope}
                onChange={(event) => setNewScope(event.target.value as "personal" | "business")}
              >
                <option value="personal">Personal</option>
                <option value="business">Business</option>
              </select>
            </label>
            <div className="flex items-end">
              <button type="submit" className="solar-btn-secondary w-full" disabled={saving}>
                Add category
              </button>
            </div>
          </form>
        ) : null}
      </section>

      <section aria-label="Budget comparison">
        <h2 className="text-lg font-semibold">Comparison</h2>
        <div className="mt-4 hidden overflow-x-auto md:block">
          <table className="min-w-[720px] w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-xs uppercase tracking-wide text-[var(--muted)]">
                <th className="px-3 py-2">Approach</th>
                <th className="px-3 py-2">Income</th>
                <th className="px-3 py-2">Mandatory</th>
                <th className="px-3 py-2">Debt min</th>
                <th className="px-3 py-2">Overpay</th>
                <th className="px-3 py-2">Buffer</th>
                <th className="px-3 py-2">Discretionary</th>
                <th className="px-3 py-2">Surplus</th>
              </tr>
            </thead>
            <tbody>
              {comparison.map((row) => (
                <tr key={row.key} className="border-b border-[var(--border)]">
                  <td className="px-3 py-2 font-medium">{row.name}</td>
                  <td className="px-3 py-2 tabular-nums">{formatGbp(row.totals.income_gbp)}</td>
                  <td className="px-3 py-2 tabular-nums">{formatGbp(row.totals.committed_gbp)}</td>
                  <td className="px-3 py-2 tabular-nums">{formatGbp(row.totals.debt_minimum_gbp)}</td>
                  <td className="px-3 py-2 tabular-nums">{formatGbp(row.totals.debt_overpayment_gbp)}</td>
                  <td className="px-3 py-2 tabular-nums">{formatGbp(row.totals.buffer_gbp)}</td>
                  <td className="px-3 py-2 tabular-nums">{formatGbp(row.totals.discretionary_gbp)}</td>
                  <td className="px-3 py-2 tabular-nums">
                    {row.totals.surplus_gbp == null
                      ? "Unavailable"
                      : formatGbp(row.totals.surplus_gbp)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4 grid gap-3 md:hidden">
          {comparison.map((row) => (
            <article key={row.key} className="rounded-xl border border-[var(--border)] px-4 py-3 text-sm">
              <h3 className="font-semibold">{row.name}</h3>
              <p className="mt-2 text-[var(--muted)]">
                Income {formatGbp(row.totals.income_gbp)} · Mandatory {formatGbp(row.totals.committed_gbp)} ·
                Overpay {formatGbp(row.totals.debt_overpayment_gbp)} · Surplus{" "}
                {row.totals.surplus_gbp == null ? "unavailable" : formatGbp(row.totals.surplus_gbp)}
              </p>
            </article>
          ))}
        </div>
      </section>

      {suggestions.saved_plans.length > 0 ? (
        <section aria-label="Saved budgets">
          <h2 className="text-lg font-semibold">Saved budgets</h2>
          <ul className="mt-3 space-y-2">
            {suggestions.saved_plans.map((plan) => (
              <li
                key={plan.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--border)] px-4 py-3 text-sm"
              >
                <button type="button" className="text-left" onClick={() => void handleSelectSaved(plan)}>
                  <span className="font-medium">{plan.name}</span>
                  {plan.is_active ? (
                    <span className="ml-2 rounded-full bg-emerald-600 px-2 py-0.5 text-xs font-semibold text-white">
                      Active
                    </span>
                  ) : (
                    <span className="ml-2 text-xs text-[var(--muted)]">Saved</span>
                  )}
                  <span className="ml-2 capitalize text-[var(--muted)]">{plan.strategy.replace("_", " ")}</span>
                </button>
                {canWrite && plan.is_active && plan.id === planId ? (
                  <button
                    type="button"
                    className="solar-btn-ghost text-sm"
                    disabled={saving}
                    onClick={() => void onDeactivate(plan.id)}
                  >
                    Leave no active budget
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {canWrite ? (
        <div className="flex flex-wrap gap-2">
          <button type="button" className="solar-btn-primary" disabled={saving} onClick={() => void handleSave(false)}>
            {saving ? "Saving…" : "Save budget"}
          </button>
          <button type="button" className="solar-btn-secondary" disabled={saving} onClick={() => void handleSave(true)}>
            Save and set active
          </button>
          {planId ? (
            <>
              <button
                type="button"
                className="solar-btn-secondary"
                disabled={saving || activeId === planId}
                onClick={() => void onActivate(planId)}
              >
                Set active
              </button>
              <button type="button" className="solar-btn-ghost" disabled={saving} onClick={() => void onDuplicate(planId)}>
                Duplicate budget
              </button>
              <button type="button" className="solar-btn-ghost" disabled={saving} onClick={() => void onReset(planId)}>
                Reset to suggested
              </button>
              <button
                type="button"
                className="solar-btn-ghost"
                disabled={saving || activeId === planId}
                onClick={() => setConfirmDelete(true)}
              >
                Delete budget
              </button>
            </>
          ) : null}
        </div>
      ) : null}

      {planId && activeId === planId ? (
        <p className="text-sm text-[var(--muted)]">
          This is the active budget. Activate another one, or leave no active budget, before deleting it.
        </p>
      ) : null}

      <ConfirmDialog
        open={confirmDelete}
        title="Delete this budget?"
        description="The saved plan will be removed. Underlying income, debts, and transactions are not changed."
        confirmLabel="Delete budget"
        onCancel={() => setConfirmDelete(false)}
        onConfirm={() => {
          setConfirmDelete(false);
          if (planId) void onDelete(planId);
        }}
      />
    </div>
  );
}

function Metric({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "good" | "bad" | "muted";
}) {
  const toneClass =
    tone === "good"
      ? "text-emerald-600 dark:text-emerald-400"
      : tone === "bad"
        ? "text-red-600 dark:text-red-400"
        : tone === "muted"
          ? "text-[var(--muted)]"
          : "";
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-sunken)]/40 px-3 py-2">
      <dt className="text-xs uppercase tracking-wide text-[var(--muted)]">{label}</dt>
      <dd className={`mt-1 text-sm font-semibold tabular-nums ${toneClass}`}>{value}</dd>
    </div>
  );
}
