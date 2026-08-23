"use client";

import { useCallback, useMemo, useState } from "react";

import { ErrorBanner, SuccessBanner } from "@/components/shared/Banners";
import { apiClient } from "@/lib/api-client";
import { useFinanceReload } from "@/lib/use-finance-reload";

type Rule = {
  pattern?: string;
  category?: string;
  scope?: string;
  match_type?: string;
  priority?: number;
};

type CategoryOption = { parent: string; scope: string };

type CategoryRulesPanelProps = {
  canEdit?: boolean;
};

export function CategoryRulesPanel({ canEdit = false }: CategoryRulesPanelProps) {
  const [rules, setRules] = useState<Rule[]>([]);
  const [categories, setCategories] = useState<CategoryOption[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [form, setForm] = useState({
    pattern: "",
    category: "Food",
    scope: "personal",
    apply_to_existing: true,
  });
  const [saving, setSaving] = useState(false);
  const [suggestions, setSuggestions] = useState<
    Array<{ scope: string; pattern: string; count: number }>
  >([]);

  const load = useCallback(async () => {
    try {
      const [ruleData, catData, suggestionData] = await Promise.all([
        apiClient.get<Rule[]>("/finance/category-rules"),
        apiClient.get<CategoryOption[]>("/finance/categories"),
        apiClient
          .get<Array<{ scope: string; pattern: string; count: number }>>(
            "/finance/category-rule-suggestions",
          )
          .catch(() => []),
      ]);
      setRules(Array.isArray(ruleData) ? ruleData : []);
      setCategories(Array.isArray(catData) ? catData : []);
      setSuggestions(Array.isArray(suggestionData) ? suggestionData : []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load category rules");
    }
  }, []);

  useFinanceReload(load, true);

  const scopedCategories = useMemo(
    () => [
      ...new Set(
        categories
          .filter((item) => item.scope === form.scope)
          .map((item) => item.parent)
          .filter(Boolean),
      ),
    ],
    [categories, form.scope],
  );

  const selectedCategory = scopedCategories.includes(form.category)
    ? form.category
    : scopedCategories[0] || form.category;

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || saving) return;
    setSaving(true);
    setStatus(null);
    try {
      const result = await apiClient.post<{
        applied?: { updated?: number; message?: string } | null;
      }>("/finance/category-rules", {
        ...form,
        category: selectedCategory,
      });
      const applied = result.applied?.updated;
      setStatus(
        applied != null
          ? `Rule saved and applied to ${applied} existing uncategorised row(s).`
          : "Rule saved — future imports will use this category.",
      );
      setForm((prev) => ({ ...prev, pattern: "" }));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save rule");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="space-y-4 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <div>
        <h2 className="text-lg font-semibold">Categorisation rules</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Confirmed merchant patterns. Manual corrections on Transactions can also create these.
        </p>
      </div>
      {error ? <ErrorBanner message={error} /> : null}
      {status ? <SuccessBanner message={status} /> : null}
      {canEdit ? (
        <form onSubmit={(event) => void save(event)} className="grid gap-3 sm:grid-cols-4">
          <input
            className="solar-input sm:col-span-2"
            placeholder="Pattern (e.g. TESLA FINANCE)"
            value={form.pattern}
            onChange={(event) => setForm({ ...form, pattern: event.target.value })}
            required
          />
          <select
            className="solar-input"
            value={form.scope}
            onChange={(event) => {
              const scope = event.target.value;
              const parents = [
                ...new Set(
                  categories
                    .filter((item) => item.scope === scope)
                    .map((item) => item.parent)
                    .filter(Boolean),
                ),
              ];
              setForm({
                ...form,
                scope,
                category: parents[0] || form.category,
              });
            }}
          >
            <option value="personal">Personal</option>
            <option value="business">Business</option>
          </select>
          <select
            className="solar-input"
            value={selectedCategory}
            onChange={(event) => setForm({ ...form, category: event.target.value })}
          >
            {scopedCategories.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-2 text-sm sm:col-span-4">
            <input
              type="checkbox"
              checked={form.apply_to_existing}
              onChange={(event) =>
                setForm({ ...form, apply_to_existing: event.target.checked })
              }
            />
            Apply to existing uncategorised transactions
          </label>
          <button type="submit" className="solar-btn-primary sm:col-span-4" disabled={saving}>
            {saving ? "Saving…" : "Add contains rule"}
          </button>
        </form>
      ) : null}
      {suggestions.length > 0 ? (
        <div>
          <h3 className="text-sm font-medium">Suggested from frequency</h3>
          <ul className="mt-2 space-y-1 text-sm text-[var(--muted)]">
            {suggestions.slice(0, 8).map((item) => (
              <li key={`${item.scope}-${item.pattern}`}>
                {item.pattern} · {item.scope} · {item.count}×
                {canEdit ? (
                  <>
                    {" "}
                    <button
                      type="button"
                      className="underline"
                      onClick={() =>
                        setForm({
                          ...form,
                          pattern: item.pattern,
                          scope: item.scope,
                        })
                      }
                    >
                      Use
                    </button>
                  </>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <ul className="space-y-2 text-sm">
        {rules.length === 0 ? (
          <li className="text-[var(--muted)]">No confirmed rules yet.</li>
        ) : (
          rules.map((rule) => (
            <li
              key={`${rule.scope}-${rule.pattern}-${rule.category}`}
              className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[var(--border)] px-3 py-2"
            >
              <span>
                <span className="font-medium">{rule.pattern}</span>
                <span className="text-[var(--muted)]">
                  {" "}
                  → {rule.category} · {rule.scope} · {rule.match_type || "CONTAINS"}
                </span>
              </span>
            </li>
          ))
        )}
      </ul>
    </section>
  );
}
