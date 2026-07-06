"use client";

import { useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { financeTransactionSchema, type FinanceTransaction } from "@/lib/finance-schemas";
import { formatGbp } from "@/lib/money";
import { z } from "zod";

type RecentTransactionsProps = {
  limit?: number;
};

export function RecentTransactions({ limit = 10 }: RecentTransactionsProps) {
  const [rows, setRows] = useState<FinanceTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoading(true);
      try {
        const data = await apiClient.get<unknown>(`/finance/transactions?limit=${limit}`);
        if (!cancelled) {
          setRows(z.array(financeTransactionSchema).parse(data));
          setError(null);
        }
      } catch {
        if (!cancelled) setError("Transactions could not be loaded.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [limit]);

  if (loading) {
    return <p className="text-sm text-[var(--muted)]">Loading recent transactions…</p>;
  }

  if (error) {
    return <p className="text-sm text-[var(--muted)]">{error}</p>;
  }

  if (!rows.length) {
    return (
      <p className="text-sm text-[var(--muted)]">
        No transactions yet. Connect a bank on Bank Connections — they import automatically on sync.
      </p>
    );
  }

  return (
    <ul className="divide-y divide-[var(--border)] rounded-xl border border-[var(--border)]">
      {rows.map((tx) => (
        <li key={tx.id} className="flex items-start justify-between gap-3 px-4 py-3 text-sm">
          <div className="min-w-0">
            <p className="truncate font-medium">
              {tx.merchant || tx.description || "Transaction"}
            </p>
            <p className="text-xs text-[var(--muted)]">
              {tx.transaction_date}
              {tx.is_pending ? " · Pending" : ""}
            </p>
          </div>
          <span
            className={`shrink-0 font-mono text-sm ${
              tx.amount_gbp < 0 ? "text-red-600 dark:text-red-400" : "text-emerald-600 dark:text-emerald-400"
            }`}
          >
            {formatGbp(tx.amount_gbp)}
          </span>
        </li>
      ))}
    </ul>
  );
}
