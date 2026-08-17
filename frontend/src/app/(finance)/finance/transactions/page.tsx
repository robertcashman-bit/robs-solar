"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";

import { SavedFiguresBanner } from "@/components/finance/SavedFiguresBanner";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner, SuccessBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { notifyFinanceChanged } from "@/lib/finance-events";
import { formatGbp } from "@/lib/money";
import { canWrite } from "@/lib/permissions";
import { useFinanceBackgroundLiveRefresh } from "@/lib/use-finance-background-live-refresh";
import { useFinanceReload } from "@/lib/use-finance-reload";

type Txn = {
  id: number;
  posted_on: string;
  description: string;
  amount_gbp: number;
  category: string;
  category_confidence?: string;
  scope: string;
  is_transfer: boolean;
  account_name: string;
};

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

export default function TransactionsPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const writable = canWrite(user);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<Txn[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [category, setCategory] = useState("Food");
  const [categories, setCategories] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError(null);
    try {
      const params = new URLSearchParams();
      if (filter === "personal" || filter === "business") {
        params.set("scope", filter);
      } else if (filter !== "all") {
        params.set("filter", filter);
      }
      if (q.trim()) params.set("q", q.trim());
      const [data, cats] = await Promise.all([
        apiClient.get<Txn[]>(`/finance/transactions?${params}`),
        apiClient.get<Array<{ parent: string }>>("/finance/categories"),
      ]);
      setRows(data);
      setCategories([...new Set(cats.map((item) => item.parent).filter(Boolean))]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load transactions");
    } finally {
      setLoading(false);
    }
  }, [filter, q]);

  useFinanceReload(load, Boolean(user) && !authLoading);
  const { refreshing } = useFinanceBackgroundLiveRefresh(user);

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
    setBusy(true);
    setError(null);
    try {
      const result = await apiClient.post<{ updated: number }>("/finance/transactions/bulk-category", {
        ids: [...selected],
        category,
        create_rule: createRule,
      });
      setMessage(`Updated ${result.updated} transaction(s)`);
      setSelected(new Set());
      notifyFinanceChanged();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bulk update failed");
    } finally {
      setBusy(false);
    }
  };

  if (authLoading || !user) {
    if (!authLoading && !user) router.replace("/login");
    return <AuthLoadingShell />;
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Transactions"
        description="Review, search, and bulk-categorise. Transfers stay out of spend totals."
      />
      <div className="mt-6 space-y-4">
        {error ? <ErrorBanner message={error} /> : null}
        {message ? <SuccessBanner message={message} /> : null}
        <SavedFiguresBanner refreshing={refreshing} />
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
                <select
                  className="mt-1 block rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                >
                  {categories.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                disabled={busy || !selected.size}
                onClick={() => void bulk(false)}
                className="rounded-lg bg-emerald-600 px-3 py-2 text-sm text-white disabled:opacity-50"
              >
                Apply to selected
              </button>
              <button
                type="button"
                disabled={busy || !selected.size}
                onClick={() => void bulk(true)}
                className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm disabled:opacity-50"
              >
                Always match like this
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void apiClient.post("/finance/transfers/detect").then(load)}
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
                    No transaction history available
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr key={row.id} className="border-b border-[var(--border)]/50">
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        checked={selected.has(row.id)}
                        onChange={() => toggle(row.id)}
                        disabled={!writable}
                      />
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">{row.posted_on}</td>
                    <td className="px-3 py-2">
                      {row.description}
                      {row.is_transfer ? (
                        <span className="ml-2 text-xs text-amber-700">transfer</span>
                      ) : null}
                    </td>
                    <td className="px-3 py-2">{formatGbp(row.amount_gbp)}</td>
                    <td className="px-3 py-2">
                      {row.category || "—"}
                      {row.category_confidence ? (
                        <span className="ml-1 text-xs text-[var(--muted)]">
                          {row.category_confidence}
                        </span>
                      ) : null}
                    </td>
                    <td className="px-3 py-2">{row.scope}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </AppShell>
  );
}
