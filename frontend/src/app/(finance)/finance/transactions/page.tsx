"use client";

import { useMemo, useState } from "react";

import { FinancePeriodScopeControl } from "@/components/finance/FinancePeriodScopeControl";
import { SavedFiguresBanner } from "@/components/finance/SavedFiguresBanner";
import { TransactionCategoryEditor } from "@/components/finance/TransactionCategoryEditor";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner, SuccessBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { apiClient } from "@/lib/api-client";
import { notifyFinanceChanged } from "@/lib/finance-events";
import { formatGbp } from "@/lib/money";
import { canWrite } from "@/lib/permissions";
import { periodDateRange } from "@/lib/finance-period";
import { useFinancePeriod } from "@/lib/use-finance-period";
import { useFinanceTransactions } from "@/lib/use-finance-transactions";
import { useRequireAuth } from "@/lib/use-require-auth";

const FILTERS = [
  "all",
  "uncategorised",
  "low_confidence",
  "personal",
  "business",
  "transfers",
  "income",
  "expenses",
  "needs_review",
] as const;

type FilterKey = (typeof FILTERS)[number];

function readQueryParam(name: string): string {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get(name) ?? "";
}

function initialFilter(): FilterKey {
  const value = readQueryParam("filter");
  return (FILTERS as readonly string[]).includes(value)
    ? (value as FilterKey)
    : "all";
}

function initialQ(): string {
  return readQueryParam("q");
}

export default function TransactionsPage() {
  const { user, gated, redirecting } = useRequireAuth();
  const writable = canWrite(user);
  const [filter, setFilter] = useState<FilterKey>(initialFilter);
  const [q, setQ] = useState(initialQ);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [category, setCategory] = useState("");
  const [newCategory, setNewCategory] = useState("");
  const [useNewCategory, setUseNewCategory] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const periodState = useFinancePeriod({ defaultScope: "both" });
  const range = periodDateRange(periodState.period);
  const {
    rows,
    categories,
    categoryOptions,
    loading,
    refreshing,
    error,
    hasMore,
    loadMore,
    reload,
    patchRow,
    setError,
  } = useFinanceTransactions(
    user,
    filter,
    q,
    range.dateFrom,
    range.dateTo,
    periodState.scope,
  );

  const bulkCategoryNames = useMemo(() => {
    if (periodState.scope === "personal" || periodState.scope === "business") {
      return categories;
    }
    if (filter === "personal" || filter === "business") {
      return [
        ...new Set(
          categoryOptions
            .filter((item) => item.scope === filter)
            .map((item) => item.parent),
        ),
      ];
    }
    return categories;
  }, [categories, categoryOptions, filter, periodState.scope]);

  const effectiveBulkCategory = bulkCategoryNames.includes(category)
    ? category
    : bulkCategoryNames[0] || "";
  const selectedCategory = useNewCategory
    ? newCategory.trim()
    : effectiveBulkCategory;

  const toggle = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const bulk = async (createRule: boolean) => {
    if (!selected.size) return;
    const nextCategory = selectedCategory.trim();
    if (!nextCategory) {
      setError("Choose or enter a category");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await apiClient.post<{ updated: number }>(
        "/finance/transactions/bulk-category",
        {
          ids: [...selected],
          category: nextCategory,
          create_rule: createRule,
        },
      );
      setMessage(`Updated ${result.updated} transaction(s)`);
      setSelected(new Set());
      setUseNewCategory(false);
      setNewCategory("");
      notifyFinanceChanged();
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bulk update failed");
    } finally {
      setBusy(false);
    }
  };

  if (gated) {
    return <AuthLoadingShell redirecting={redirecting} />;
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Transactions"
        description="Review, search, and recategorise. Transfers stay out of spend totals."
      />
      <div className="mt-6 space-y-4">
        {error ? <ErrorBanner message={error} /> : null}
        {message ? <SuccessBanner message={message} /> : null}
        <SavedFiguresBanner refreshing={refreshing} />
        <FinancePeriodScopeControl
          period={periodState.period}
          onPeriodChange={periodState.setPeriod}
          scope={periodState.scope}
          onScopeChange={periodState.setScope}
        />
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setFilter(item)}
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                filter === item
                  ? "bg-emerald-600 text-white"
                  : "border border-[var(--border)] text-[var(--muted)]"
              }`}
            >
              {item.replace("_", " ")}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="text-[var(--muted)]">Search</span>
            <input
              className="mt-1 block rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="merchant, amount…"
            />
          </label>
          {writable ? (
            <>
              <label className="text-sm">
                <span className="text-[var(--muted)]">Set category</span>
                {useNewCategory ? (
                  <input
                    className="mt-1 block rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value)}
                    placeholder="New category name"
                    aria-label="New bulk category name"
                  />
                ) : (
                  <select
                    className="mt-1 block rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
                    value={effectiveBulkCategory}
                    onChange={(e) => {
                      if (e.target.value === "__new__") {
                        setUseNewCategory(true);
                        setNewCategory("");
                        return;
                      }
                      setCategory(e.target.value);
                    }}
                  >
                    {bulkCategoryNames.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                    <option value="__new__">Add new category…</option>
                  </select>
                )}
              </label>
              {useNewCategory ? (
                <button
                  type="button"
                  className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
                  onClick={() => {
                    setUseNewCategory(false);
                    setNewCategory("");
                  }}
                >
                  Pick existing
                </button>
              ) : null}
              <button
                type="button"
                disabled={busy || !selected.size || !selectedCategory}
                onClick={() => void bulk(false)}
                className="rounded-lg bg-emerald-600 px-3 py-2 text-sm text-white disabled:opacity-50"
              >
                Apply to selected
              </button>
              <button
                type="button"
                disabled={busy || !selected.size || !selectedCategory}
                onClick={() => void bulk(true)}
                className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm disabled:opacity-50"
              >
                Always match like this
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  void apiClient
                    .post("/finance/transfers/detect")
                    .then(() => reload())
                }
                className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
              >
                Detect transfers
              </button>
            </>
          ) : null}
        </div>
        <div className="overflow-x-auto rounded-2xl border border-[var(--border)] bg-[var(--surface)]">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-[var(--border)] text-[var(--muted)]">
              <tr>
                <th className="px-3 py-2" />
                <th className="px-3 py-2">Date</th>
                <th className="px-3 py-2">Description</th>
                <th className="px-3 py-2">Amount</th>
                <th className="px-3 py-2">Category</th>
                <th className="px-3 py-2">Scope</th>
              </tr>
            </thead>
            <tbody>
              {loading && rows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-3 py-6 text-[var(--muted)]">
                    Loading transactions…
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-3 py-6 text-[var(--muted)]">
                    No transactions imported yet.
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr
                    key={row.id}
                    className="border-b border-[var(--border)]/50"
                  >
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        checked={selected.has(row.id)}
                        onChange={() => toggle(row.id)}
                        disabled={!writable}
                      />
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      {row.posted_on}
                    </td>
                    <td className="px-3 py-2">
                      {row.description}
                      {row.is_transfer ? (
                        <span className="ml-2 text-xs text-amber-700">
                          transfer
                        </span>
                      ) : null}
                    </td>
                    <td className="px-3 py-2">{formatGbp(row.amount_gbp)}</td>
                    <td className="px-3 py-2">
                      <TransactionCategoryEditor
                        txnId={row.id}
                        scope={row.scope}
                        category={row.category}
                        categoryConfidence={row.category_confidence}
                        options={categoryOptions}
                        canEdit={writable}
                        disabled={busy}
                        onError={(msg) => setError(msg)}
                        onUpdated={(next) => {
                          setMessage(`Category set to ${next.category}`);
                          patchRow(row.id, {
                            category: next.category,
                            category_confidence: next.category_confidence,
                            scope: row.scope,
                          });
                          notifyFinanceChanged();
                        }}
                      />
                    </td>
                    <td className="px-3 py-2">{row.scope}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {hasMore ? (
          <button
            type="button"
            className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
            onClick={() => void loadMore()}
          >
            Load more
          </button>
        ) : null}
      </div>
    </AppShell>
  );
}
