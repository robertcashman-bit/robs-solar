"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { MonthlyBudgetPanel } from "@/components/finance/MonthlyBudgetPanel";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { ErrorBanner, SuccessBanner } from "@/components/shared/Banners";
import { apiClient } from "@/lib/api-client";
import { summariseBudgetLines } from "@/lib/budget-totals";
import {
  budgetCompareSchema,
  budgetPlanSchema,
  budgetSuggestionsSchema,
  budgetVsActualSchema,
  type BudgetCompare,
  type BudgetPlan,
  type BudgetPlanLine,
  type BudgetSuggestions,
  type BudgetVsActual,
  type SuggestedBudgetOption,
} from "@/lib/finance-schemas";
import { notifyFinanceChanged } from "@/lib/finance-events";
import { currentMonthKey, formatGbp, parseMoneyInput } from "@/lib/money";
import { canWrite } from "@/lib/permissions";
import type { UserInfo } from "@/lib/schemas";

type Tab = "month" | "suggested" | "editor" | "compare" | "actual";

type DraftLine = BudgetPlanLine & { amount_text: string };

function toDraftLine(line: BudgetPlanLine): DraftLine {
  return { ...line, amount_text: String(line.amount_gbp) };
}

const PERSONAL_CATEGORIES = [
  "Household / mortgage contribution",
  "Utilities",
  "Food",
  "Transport",
  "Insurance",
  "Phone / communications",
  "Family support",
  "Debt minimum payments",
  "Debt overpayments",
  "Personal spending",
  "Subscriptions",
  "Emergency buffer",
  "Savings",
  "Other",
];

const BUSINESS_CATEGORIES = [
  "Salary",
  "Vehicle finance",
  "Loan repayments",
  "Software / IT",
  "Telephone",
  "Insurance",
  "Professional costs",
  "Travel",
  "Accountancy",
  "Tax reserve",
  "VAT reserve",
  "Corporation tax reserve",
  "Debt overpayment",
  "Business buffer",
  "Other operating expenses",
];

function emptyLine(scope: "personal" | "business", category: string): DraftLine {
  return {
    id: null,
    scope,
    category,
    amount_gbp: 0,
    amount_text: "0",
    source: "user",
    source_note: "User-entered",
    is_custom: true,
    sort_order: 200,
    subcategory: "",
    basis_json: "{}",
    confidence: "",
    insufficient_data: false,
  };
}

export function BudgetStudio({ user }: { user: UserInfo | null }) {
  const writable = canWrite(user);
  const [tab, setTab] = useState<Tab>("month");
  const [month, setMonth] = useState(currentMonthKey());
  const [suggestions, setSuggestions] = useState<BudgetSuggestions | null>(null);
  const [plans, setPlans] = useState<BudgetPlan[]>([]);
  const [compare, setCompare] = useState<BudgetCompare | null>(null);
  const [actual, setActual] = useState<BudgetVsActual | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const [planId, setPlanId] = useState<number | null>(null);
  const [name, setName] = useState("Custom budget");
  const [style, setStyle] = useState("custom");
  const [explanation, setExplanation] = useState("Your own figures, starting from recorded finances or a blank plan.");
  const [incomeText, setIncomeText] = useState("0");
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [intensity, setIntensity] = useState("medium");
  const [dirty, setDirty] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [newCategory, setNewCategory] = useState("");
  const [newScope, setNewScope] = useState<"personal" | "business">("personal");
  const [actualDrafts, setActualDrafts] = useState<Record<string, string>>({});
  const [extraActual, setExtraActual] = useState({
    scope: "personal" as "personal" | "business",
    category: "",
    amount: "",
  });
  const [savingActuals, setSavingActuals] = useState(false);
  const [hydratedEditor, setHydratedEditor] = useState(false);

  const totals = useMemo(() => {
    const incomeValue = parseMoneyInput(incomeText);
    const amounts = lines.map((line) => parseMoneyInput(line.amount_text));
    if (incomeValue == null || amounts.some((value) => value == null)) {
      return null;
    }
    return summariseBudgetLines(
      lines.map((line, index) => ({
        category: line.category,
        amount_gbp: amounts[index] as number,
      })),
      incomeValue,
    );
  }, [incomeText, lines]);

  const recommended = useMemo(
    () => suggestions?.options.find((item) => item.recommended) ?? suggestions?.options[0] ?? null,
    [suggestions],
  );

  const load = useCallback(async () => {
    try {
      const suggestionData = await apiClient.get<unknown>("/finance/budgets/suggestions");
      const parsedSuggestions = budgetSuggestionsSchema.parse(suggestionData);
      const [planData, compareData, actualData] = await Promise.all([
        apiClient.get<unknown>("/finance/budgets"),
        apiClient.get<unknown>("/finance/budgets/compare"),
        apiClient.get<unknown>(`/finance/budgets/vs-actual?month=${month}`),
      ]);
      setSuggestions(parsedSuggestions);
      setPlans(budgetPlanSchema.array().parse(planData));
      setCompare(budgetCompareSchema.parse(compareData));
      const parsedActual = budgetVsActualSchema.parse(actualData);
      setActual(parsedActual);
      setActualDrafts(
        Object.fromEntries(
          parsedActual.lines.map((line) => [
            `${line.scope}:${line.category}`,
            line.actual_gbp ? String(line.actual_gbp) : "",
          ]),
        ),
      );
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load budgets");
    } finally {
      setLoaded(true);
    }
  }, [month]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    const onChanged = () => {
      void load();
    };
    window.addEventListener("robs-finance-changed", onChanged);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("robs-finance-changed", onChanged);
    };
  }, [load]);

  useEffect(() => {
    if (!loaded || hydratedEditor || dirty) return;
    const active = plans.find((item) => item.is_active);
    const timer = window.setTimeout(() => {
      if (active) {
        fillFromPlan(active);
      } else if (plans.length === 0) {
        setTab("suggested");
      }
      setHydratedEditor(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [dirty, hydratedEditor, loaded, plans]);

  function applyOption(option: SuggestedBudgetOption, asCustom = false) {
    setPlanId(null);
    setName(asCustom ? `Custom from ${option.name}` : option.name);
    setStyle(asCustom ? "custom" : option.style);
    setExplanation(option.explanation);
    setIncomeText(String(option.income_gbp));
    setLines(option.lines.map(toDraftLine));
    setIntensity(option.debt_intensity);
    setDirty(true);
    setTab("editor");
    setStatus(null);
  }

  function fillFromPlan(plan: BudgetPlan) {
    setPlanId(plan.id);
    setName(plan.name);
    setStyle(plan.style);
    setExplanation(plan.explanation);
    setIncomeText(String(plan.income_gbp));
    setLines(plan.lines.map(toDraftLine));
    setIntensity(plan.debt_intensity);
    setDirty(false);
  }

  function applyPlan(plan: BudgetPlan) {
    fillFromPlan(plan);
    setTab("editor");
    setStatus(null);
  }

  function startBlank() {
    setPlanId(null);
    setName("Custom budget");
    setStyle("custom");
    setExplanation("Start from your own category amounts.");
    setIncomeText(String(suggestions?.income_gbp ?? 0));
    setLines([]);
    setIntensity("medium");
    setDirty(true);
    setTab("editor");
  }

  function updateLine(index: number, amount: string) {
    const parsed = parseMoneyInput(amount);
    setLines((current) =>
      current.map((line, i) =>
        i === index
          ? { ...line, amount_text: amount, amount_gbp: parsed ?? line.amount_gbp }
          : line,
      ),
    );
    setDirty(true);
  }

  function removeLine(index: number) {
    setLines((current) => current.filter((_, i) => i !== index));
    setDirty(true);
  }

  function addCategory(event: React.FormEvent) {
    event.preventDefault();
    const category = newCategory.trim();
    if (!category) return;
    setLines((current) => [...current, emptyLine(newScope, category)]);
    setNewCategory("");
    setDirty(true);
  }

  async function savePlan(activate = false) {
    if (!writable || saving) return;
    const incomeValue = parseMoneyInput(incomeText);
    const lineAmounts = lines.map((line) => parseMoneyInput(line.amount_text));
    if (incomeValue == null || lineAmounts.some((value) => value == null) || !totals) {
      setError("Enter valid pound amounts for income and every category. Invalid text is not saved as £0.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload = {
        name,
        style: style === "custom" ? "custom" : style,
        notes: "",
        explanation,
        debt_intensity: intensity,
        cash_buffer_target_gbp: totals.buffer_gbp,
        discretionary_gbp: totals.discretionary_gbp,
        tax_reserve_gbp: totals.tax_reserve_gbp,
        income_gbp: incomeValue,
        lines: lines.map((line, index) => ({
          scope: line.scope,
          category: line.category,
          amount_gbp: lineAmounts[index] as number,
          source: line.source,
          source_note: line.source_note,
          is_custom: line.is_custom,
          sort_order: line.sort_order || index * 10,
        })),
      };
      const saved = planId
        ? budgetPlanSchema.parse(await apiClient.put(`/finance/budgets/${planId}`, payload))
        : budgetPlanSchema.parse(await apiClient.post("/finance/budgets", payload));
      setPlanId(saved.id);
      setIncomeText(String(saved.income_gbp));
      setLines(saved.lines.map(toDraftLine));
      if (activate) {
        await apiClient.post(`/finance/budgets/${saved.id}/activate`);
      }
      setDirty(false);
      setStatus(activate ? "Budget saved and set as active" : "Budget saved");
      notifyFinanceChanged();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save budget");
    } finally {
      setSaving(false);
    }
  }

  async function duplicatePlan() {
    if (!writable || planId == null) return;
    try {
      const copy = budgetPlanSchema.parse(await apiClient.post(`/finance/budgets/${planId}/duplicate`));
      applyPlan(copy);
      setDirty(true);
      setStatus("Budget duplicated — rename and save if you want a lasting copy");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to duplicate budget");
    }
  }

  async function activatePlan() {
    if (!writable || planId == null) {
      await savePlan(true);
      return;
    }
    try {
      await apiClient.post(`/finance/budgets/${planId}/activate`);
      setStatus("Active budget updated");
      notifyFinanceChanged();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to activate budget");
    }
  }

  async function saveSuggestion(option: SuggestedBudgetOption, activate = true) {
    if (!writable || saving) return;
    setSaving(true);
    setError(null);
    try {
      const existing = plans.find(
        (plan) => plan.style === option.style && plan.origin === "suggested",
      );
      const saved = existing
        ? budgetPlanSchema.parse(
            activate
              ? await apiClient.post(`/finance/budgets/${existing.id}/activate`)
              : existing,
          )
        : budgetPlanSchema.parse(
            await apiClient.post("/finance/budgets/from-suggestion", {
              style: option.style,
              name: option.name,
              activate,
            }),
          );
      fillFromPlan(saved);
      setTab("editor");
      setStatus(activate ? "Budget saved and set as active" : "Budget saved");
      notifyFinanceChanged();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save suggested budget");
    } finally {
      setSaving(false);
    }
  }

  async function deletePlan() {
    if (!writable || planId == null) return;
    try {
      await apiClient.delete(`/finance/budgets/${planId}`);
      startBlank();
      setStatus("Budget deleted");
      setConfirmDelete(false);
      notifyFinanceChanged();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete budget");
    }
  }

  function resetSuggestion() {
    const option = suggestions?.options.find((item) => item.style === style);
    if (option) applyOption(option);
  }

  function actualKey(scope: string, category: string) {
    return `${scope}:${category}`;
  }

  function parsedActualAmount(key: string) {
    const raw = actualDrafts[key] ?? "";
    if (!raw.trim()) {
      return undefined;
    }
    return parseMoneyInput(raw);
  }

  async function saveActuals() {
    if (!writable || !actual || savingActuals) return;
    const prepared = actual.lines.map((line) => ({
      line,
      amount: parsedActualAmount(actualKey(line.scope, line.category)),
    }));
    if (prepared.some((item) => item.amount === null)) {
      setError("Actual must be a number, or left blank if not recorded yet.");
      return;
    }
    const toSave = prepared.filter((item) => item.amount != null);
    if (toSave.length === 0) {
      setError("Enter at least one actual amount. Blank lines stay missing, not £0.");
      return;
    }
    setSavingActuals(true);
    setError(null);
    try {
      await apiClient.put("/finance/budget/batch", {
        lines: toSave.map((item) => ({
          scope: item.line.scope,
          month: actual.month,
          category: item.line.category,
          budgeted_gbp: item.line.budget_gbp,
          actual_gbp: item.amount as number,
        })),
      });
      setStatus("Actual spend saved");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save actual spend");
    } finally {
      setSavingActuals(false);
    }
  }

  async function addActualCategory(event: React.FormEvent) {
    event.preventDefault();
    if (!writable || !actual || savingActuals) return;
    const category = extraActual.category.trim();
    const amount = parseMoneyInput(extraActual.amount);
    if (!category || amount == null) {
      setError("Enter a category and a valid actual amount");
      return;
    }
    setSavingActuals(true);
    setError(null);
    try {
      const existing = actual.lines.find(
        (line) =>
          line.scope === extraActual.scope &&
          line.category.toLowerCase() === category.toLowerCase(),
      );
      await apiClient.put("/finance/budget", {
        scope: extraActual.scope,
        month: actual.month,
        category,
        budgeted_gbp: existing?.budget_gbp ?? 0,
        actual_gbp: amount,
      });
      setExtraActual({ scope: extraActual.scope, category: "", amount: "" });
      setStatus("Actual spend saved");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save actual spend");
    } finally {
      setSavingActuals(false);
    }
  }

  const surplusLabel =
    totals == null
      ? "Enter valid pound amounts to see surplus"
      : totals.surplus_gbp >= 0
        ? `Monthly surplus: ${formatGbp(totals.surplus_gbp)}`
        : `Monthly deficit: ${formatGbp(Math.abs(totals.surplus_gbp))}`;

  return (
    <div className="space-y-6">
      {error ? <ErrorBanner message={error} /> : null}
      {status ? <SuccessBanner message={status} /> : null}

      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Budget views">
        {(
          [
            ["month", "This month"],
            ["suggested", "Suggested"],
            ["editor", "Edit"],
            ["compare", "Compare"],
            ["actual", "vs Actual"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            className={`solar-btn-ghost ${tab === key ? "ring-2 ring-emerald-500" : ""}`}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {!loaded ? <p className="text-sm text-[var(--muted)]">Loading budgets…</p> : null}

      {loaded && plans.length === 0 ? (
        <section className="rounded-2xl border border-emerald-400/40 bg-emerald-500/10 p-5">
          <h2 className="text-lg font-semibold">Create your first budget</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Stabilise, Balanced, and Debt Attack are built from live income and recorded debts.
            Missing bills and actuals stay blank — they are not saved as £0.
          </p>
          {writable ? (
            <div className="mt-4 flex flex-wrap gap-2">
              <button type="button" className="solar-btn-primary" onClick={() => setTab("suggested")}>
                Choose a plan
              </button>
              {recommended && recommended.income_gbp > 0 ? (
                <button
                  type="button"
                  className="solar-btn-ghost"
                  disabled={saving}
                  onClick={() => void saveSuggestion(recommended, true)}
                >
                  {saving ? "Saving…" : `Save recommended ${recommended.name} and set active`}
                </button>
              ) : null}
            </div>
          ) : null}
        </section>
      ) : null}

      {tab === "month" ? (
        <MonthlyBudgetPanel
          month={month}
          onMonthChange={setMonth}
          writable={writable}
          onStatus={setStatus}
          onError={setError}
        />
      ) : null}

      {tab === "suggested" && suggestions ? (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Budget options</h2>
          {suggestions.gaps.length > 0 ? (
            <div className="rounded-xl border border-amber-400/35 bg-amber-500/10 px-4 py-3 text-sm">
              <p className="font-medium">Some suggested figures are incomplete</p>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {suggestions.gaps.map((gap) => (
                  <li key={gap.field}>
                    {gap.message}{" "}
                    <Link href={gap.href} className="underline">
                      Fill in
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <div className="grid gap-4 md:grid-cols-2">
            {suggestions.options.map((option) => (
              <article
                key={option.style}
                className={`rounded-2xl border p-4 ${
                  option.recommended ? "border-emerald-400/50 bg-emerald-500/10" : "border-[var(--border)] bg-[var(--surface)]"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold">{option.name}</h3>
                    <p className="mt-1 text-sm text-[var(--muted)]">{option.explanation}</p>
                  </div>
                  {option.recommended ? (
                    <span className="rounded-full bg-emerald-600 px-2 py-0.5 text-xs font-medium text-white">
                      Recommended
                    </span>
                  ) : null}
                </div>
                <dl className="mt-4 grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <dt className="text-[var(--muted)]">Surplus</dt>
                    <dd className="font-semibold tabular-nums">{formatGbp(option.surplus_gbp)}</dd>
                  </div>
                  <div>
                    <dt className="text-[var(--muted)]">Debt overpay</dt>
                    <dd className="font-semibold tabular-nums">{formatGbp(option.debt_overpayment_gbp)}</dd>
                  </div>
                  <div>
                    <dt className="text-[var(--muted)]">Buffer</dt>
                    <dd className="font-semibold tabular-nums">{formatGbp(option.cash_buffer_target_gbp)}</dd>
                  </div>
                  <div>
                    <dt className="text-[var(--muted)]">Discretionary</dt>
                    <dd className="font-semibold tabular-nums">{formatGbp(option.discretionary_gbp)}</dd>
                  </div>
                </dl>
                {option.shortfall_gbp > 0 ? (
                  <p className="mt-3 text-sm text-amber-800 dark:text-amber-200">
                    Projected shortfall {formatGbp(option.shortfall_gbp)}
                  </p>
                ) : null}
                {option.notes ? <p className="mt-2 text-xs text-[var(--muted)]">{option.notes}</p> : null}
                <div className="mt-4 flex flex-wrap gap-2">
                  <button type="button" className="solar-btn-primary text-sm" onClick={() => applyOption(option)}>
                    Use {option.name}
                  </button>
                  <button
                    type="button"
                    className="solar-btn-ghost text-sm"
                    disabled={saving || !writable || option.income_gbp <= 0}
                    onClick={() => void saveSuggestion(option, true)}
                  >
                    Save and set active
                  </button>
                  <button type="button" className="solar-btn-ghost text-sm" onClick={() => applyOption(option, true)}>
                    Customise
                  </button>
                </div>
              </article>
            ))}
            <article className="rounded-2xl border border-dashed border-[var(--border)] p-4">
              <h3 className="text-lg font-semibold">Custom</h3>
              <p className="mt-1 text-sm text-[var(--muted)]">
                Build your own plan from current spending, a suggested option, or a blank sheet.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <button type="button" className="solar-btn-primary text-sm" onClick={startBlank}>
                  Start blank
                </button>
                {suggestions.options[1] ? (
                  <button
                    type="button"
                    className="solar-btn-ghost text-sm"
                    onClick={() => applyOption(suggestions.options[1], true)}
                  >
                    Start from Balanced
                  </button>
                ) : null}
              </div>
            </article>
          </div>
          {plans.length > 0 ? (
            <section>
              <h3 className="solar-section-title">Saved budgets</h3>
              <ul className="mt-3 space-y-2">
                {plans.map((plan) => (
                  <li key={plan.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[var(--border)] px-4 py-3">
                    <div>
                      <p className="font-medium">
                        {plan.name}{" "}
                        {plan.is_active ? (
                          <span className="text-xs uppercase tracking-wide text-emerald-700 dark:text-emerald-300">
                            Active
                          </span>
                        ) : null}
                      </p>
                      <p className="text-xs text-[var(--muted)]">
                        {plan.style.replaceAll("_", " ")} · surplus {formatGbp(plan.totals.surplus_gbp)}
                      </p>
                    </div>
                    <button type="button" className="solar-btn-ghost text-sm" onClick={() => applyPlan(plan)}>
                      Open
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </section>
      ) : null}

      {tab === "editor" ? (
        <section className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm font-medium">
              Budget name
              <input
                className="solar-input"
                value={name}
                onChange={(event) => {
                  setName(event.target.value);
                  setDirty(true);
                }}
              />
            </label>
            <label className="text-sm font-medium">
              Monthly income
              <input
                className="solar-input"
                inputMode="decimal"
                aria-label="Monthly income"
                value={incomeText}
                onChange={(event) => {
                  setIncomeText(event.target.value);
                  setDirty(true);
                }}
              />
            </label>
          </div>
          <p className="text-sm text-[var(--muted)]">{explanation}</p>
          <div
            className={`rounded-2xl border px-4 py-3 text-lg font-semibold ${
              totals == null
                ? "border-amber-400/40 bg-amber-500/10"
                : totals.surplus_gbp >= 0
                  ? "border-emerald-400/40 bg-emerald-500/10"
                  : "border-amber-400/40 bg-amber-500/10"
            }`}
            aria-live="polite"
          >
            {surplusLabel}
            {totals && totals.shortfall_gbp > 0 ? (
              <span className="mt-1 block text-sm font-normal">
                Pressure comes from committed spending of {formatGbp(totals.committed_gbp)} plus
                discretionary {formatGbp(totals.discretionary_gbp)} against income of {formatGbp(totals.income_gbp)}.
              </span>
            ) : null}
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <fieldset className="rounded-xl border border-[var(--border)] p-3">
              <legend className="px-1 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
                Debt repayment intensity
              </legend>
              <div className="flex flex-wrap gap-2">
                {(["low", "medium", "high"] as const).map((value) => (
                  <label key={value} className="inline-flex items-center gap-1 text-sm capitalize">
                    <input
                      type="radio"
                      name="intensity"
                      checked={intensity === value}
                      onChange={() => {
                        setIntensity(value);
                        setDirty(true);
                      }}
                    />
                    {value}
                  </label>
                ))}
              </div>
              <p className="mt-2 text-xs text-[var(--muted)]">
                Overpayment {formatGbp(totals?.debt_overpayment_gbp)} — edit the category to change the amount.
              </p>
            </fieldset>
            <label className="text-sm font-medium">
              Cash buffer (calculated)
              <input className="solar-input" readOnly value={formatGbp(totals?.buffer_gbp)} />
            </label>
            <label className="text-sm font-medium">
              Discretionary (calculated)
              <input className="solar-input" readOnly value={formatGbp(totals?.discretionary_gbp)} />
            </label>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-[var(--muted)]">
                  <th className="py-2 pr-3">Category</th>
                  <th className="py-2 pr-3">Scope</th>
                  <th className="py-2 pr-3">Amount</th>
                  <th className="py-2 pr-3">Source</th>
                  <th className="py-2"> </th>
                </tr>
              </thead>
              <tbody>
                {lines.map((line, index) => (
                  <tr key={`${line.scope}-${line.category}-${index}`} className="border-b border-[var(--border)]">
                    <td className="py-2 pr-3">{line.category}</td>
                    <td className="py-2 pr-3 capitalize">{line.scope}</td>
                    <td className="py-2 pr-3">
                      <input
                        className="solar-input w-28"
                        inputMode="decimal"
                        aria-label={`${line.category} amount`}
                        value={line.amount_text}
                        onChange={(event) => updateLine(index, event.target.value)}
                      />
                    </td>
                    <td className="py-2 pr-3 text-xs text-[var(--muted)]" title={line.source_note}>
                      {line.source_note || line.source}
                    </td>
                    <td className="py-2">
                      {line.is_custom || line.category === "Other" ? (
                        <button type="button" className="solar-btn-ghost text-xs" onClick={() => removeLine(index)}>
                          Remove
                        </button>
                      ) : (
                        <button type="button" className="solar-btn-ghost text-xs" onClick={() => removeLine(index)}>
                          Remove
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {lines.length === 0 ? (
              <p className="mt-3 text-sm text-[var(--muted)]">No categories yet. Add one or choose a suggested budget.</p>
            ) : null}
          </div>
          <form onSubmit={addCategory} className="flex flex-wrap gap-2">
            <select className="solar-input" value={newScope} onChange={(event) => setNewScope(event.target.value as "personal" | "business")}>
              <option value="personal">Personal</option>
              <option value="business">Business</option>
            </select>
            <input
              className="solar-input"
              list="budget-categories"
              placeholder="Add category"
              value={newCategory}
              onChange={(event) => setNewCategory(event.target.value)}
            />
            <datalist id="budget-categories">
              {(newScope === "personal" ? PERSONAL_CATEGORIES : BUSINESS_CATEGORIES).map((item) => (
                <option key={item} value={item} />
              ))}
            </datalist>
            <button type="submit" className="solar-btn-ghost">
              Add category
            </button>
          </form>
          {writable ? (
            <div className="flex flex-wrap gap-2">
              <button type="button" className="solar-btn-primary" disabled={saving} onClick={() => void savePlan(false)}>
                {saving ? "Saving…" : "Save"}
              </button>
              <button type="button" className="solar-btn-ghost" disabled={saving} onClick={() => void savePlan(true)}>
                Save and set active
              </button>
              <button type="button" className="solar-btn-ghost" onClick={() => void activatePlan()}>
                Set active
              </button>
              <button type="button" className="solar-btn-ghost" disabled={planId == null} onClick={() => void duplicatePlan()}>
                Duplicate
              </button>
              {style !== "custom" ? (
                <button type="button" className="solar-btn-ghost" onClick={resetSuggestion}>
                  Reset suggested option
                </button>
              ) : null}
              {dirty ? (
                <button
                  type="button"
                  className="solar-btn-ghost"
                  onClick={() => {
                    const plan = plans.find((item) => item.id === planId);
                    if (plan) applyPlan(plan);
                    else if (suggestions) {
                      const option = suggestions.options.find((item) => item.style === style);
                      if (option) applyOption(option);
                    }
                    setDirty(false);
                  }}
                >
                  Revert unsaved changes
                </button>
              ) : null}
              {planId != null ? (
                <button type="button" className="solar-btn-ghost" onClick={() => setConfirmDelete(true)}>
                  Delete
                </button>
              ) : null}
            </div>
          ) : null}
        </section>
      ) : null}

      {tab === "compare" && compare ? (
        <section className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-[var(--muted)]">
                <th className="py-2 pr-3">Budget</th>
                <th className="py-2 pr-3">Spending</th>
                <th className="py-2 pr-3">Surplus</th>
                <th className="py-2 pr-3">Debt overpay</th>
                <th className="py-2 pr-3">Buffer</th>
                <th className="py-2">Discretionary</th>
              </tr>
            </thead>
            <tbody>
              {compare.rows.map((row) => (
                <tr key={row.key} className="border-b border-[var(--border)]">
                  <td className="py-2 pr-3">
                    {row.name}
                    {row.is_active ? " · Active" : ""}
                  </td>
                  <td className="py-2 pr-3 tabular-nums">{formatGbp(row.monthly_total_gbp)}</td>
                  <td className="py-2 pr-3 tabular-nums">{formatGbp(row.surplus_gbp)}</td>
                  <td className="py-2 pr-3 tabular-nums">{formatGbp(row.debt_overpayment_gbp)}</td>
                  <td className="py-2 pr-3 tabular-nums">{formatGbp(row.buffer_gbp)}</td>
                  <td className="py-2 tabular-nums">{formatGbp(row.discretionary_gbp)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}

      {tab === "actual" && actual ? (
        <section className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-[var(--muted)]">
              Record what you actually spent in {actual.month}
              {actual.plan_name ? ` against ${actual.plan_name}` : ""}. Saved actuals stay on the
              monthly budget lines and survive reload.
            </p>
            <label className="text-sm">
              <span className="sr-only">Month</span>
              <input
                type="month"
                className="solar-input text-sm"
                value={month}
                onChange={(event) => setMonth(event.target.value)}
              />
            </label>
          </div>
          {actual.lines.length > 0 ? (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void saveActuals();
              }}
            >
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] text-[var(--muted)]">
                    <th className="py-2 pr-3">Category</th>
                    <th className="py-2 pr-3">Budget</th>
                    <th className="py-2 pr-3">Actual</th>
                    <th className="py-2 pr-3">Variance</th>
                    <th className="py-2">Used</th>
                  </tr>
                </thead>
                <tbody>
                  {actual.lines.map((line) => {
                    const key = actualKey(line.scope, line.category);
                    const amount = parsedActualAmount(key);
                    const variance = amount == null ? null : line.budget_gbp - amount;
                    const used =
                      amount == null || !line.budget_gbp
                        ? null
                        : Math.round((amount / line.budget_gbp) * 1000) / 10;
                    return (
                      <tr key={key} className="border-b border-[var(--border)]">
                        <td className="py-2 pr-3">
                          {line.category}
                          <span className="ml-2 text-xs text-[var(--muted)]">{line.scope}</span>
                        </td>
                        <td className="py-2 pr-3 tabular-nums">{formatGbp(line.budget_gbp)}</td>
                        <td className="py-2 pr-3">
                          <label className="sr-only" htmlFor={`actual-${key}`}>
                            {line.category} actual
                          </label>
                          <input
                            id={`actual-${key}`}
                            className="solar-input w-28"
                            inputMode="decimal"
                            value={actualDrafts[key] ?? ""}
                            placeholder={line.missing_actual ? "Missing" : undefined}
                            disabled={!writable}
                            onChange={(event) =>
                              setActualDrafts((current) => ({
                                ...current,
                                [key]: event.target.value,
                              }))
                            }
                          />
                        </td>
                        <td className="py-2 pr-3 tabular-nums">{formatGbp(variance)}</td>
                        <td className="py-2">{used == null ? "—" : `${used}%`}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {writable ? (
                <button type="submit" className="solar-btn-primary mt-4" disabled={savingActuals}>
                  {savingActuals ? "Saving…" : "Save actuals"}
                </button>
              ) : null}
            </form>
          ) : (
            <p className="text-sm text-[var(--muted)]">
              Set an active budget, or add a category below, to record actual spend.
            </p>
          )}
          {writable ? (
            <form
              onSubmit={(event) => void addActualCategory(event)}
              className="grid gap-3 rounded-2xl border border-[var(--border)] p-4 sm:grid-cols-4"
            >
              <label className="text-sm font-medium">
                Scope
                <select
                  className="solar-input"
                  value={extraActual.scope}
                  onChange={(event) =>
                    setExtraActual({
                      ...extraActual,
                      scope: event.target.value as "personal" | "business",
                    })
                  }
                >
                  <option value="personal">Personal</option>
                  <option value="business">Business</option>
                </select>
              </label>
              <label className="text-sm font-medium">
                Category
                <input
                  className="solar-input"
                  value={extraActual.category}
                  onChange={(event) =>
                    setExtraActual({ ...extraActual, category: event.target.value })
                  }
                />
              </label>
              <label className="text-sm font-medium">
                Actual amount
                <input
                  className="solar-input"
                  inputMode="decimal"
                  value={extraActual.amount}
                  onChange={(event) =>
                    setExtraActual({ ...extraActual, amount: event.target.value })
                  }
                />
              </label>
              <button type="submit" className="solar-btn-secondary self-end" disabled={savingActuals}>
                {savingActuals ? "Saving…" : "Add actual"}
              </button>
            </form>
          ) : null}
        </section>
      ) : null}

      <ConfirmDialog
        open={confirmDelete}
        title="Delete this budget?"
        description="The saved plan will be removed. Suggested options can be generated again from your records."
        confirmLabel="Delete budget"
        onCancel={() => setConfirmDelete(false)}
        onConfirm={() => void deletePlan()}
      />
    </div>
  );
}
