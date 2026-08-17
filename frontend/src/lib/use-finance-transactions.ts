"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { notifyFinanceOverviewReady } from "@/lib/finance-events";
import { useFinanceBackgroundLiveRefresh } from "@/lib/use-finance-background-live-refresh";
import { useFinanceReload } from "@/lib/use-finance-reload";
import type { UserInfo } from "@/lib/schemas";

export type FinanceTxn = {
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

export const FINANCE_TXN_PAGE_SIZE = 50;
const LAST_TXNS_KEY = "robs-finance-last-transactions";

type CachedTxns = {
  filter: string;
  q: string;
  rows: FinanceTxn[];
  categories: string[];
  hasMore: boolean;
};

function readLastTxns(filter: string, q: string): CachedTxns | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(LAST_TXNS_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CachedTxns;
    if (parsed.filter !== filter || parsed.q !== q) return null;
    if (!Array.isArray(parsed.rows)) return null;
    return parsed;
  } catch {
    return null;
  }
}

function writeLastTxns(payload: CachedTxns): void {
  try {
    window.localStorage.setItem(LAST_TXNS_KEY, JSON.stringify(payload));
  } catch {
    // ignore private mode / quota
  }
}

export function useFinanceTransactions(
  user: UserInfo | null | undefined,
  filter: string,
  q: string,
) {
  const enabled = Boolean(user);
  const cached = enabled ? readLastTxns(filter, q.trim()) : null;
  const [rows, setRows] = useState<FinanceTxn[]>(cached?.rows ?? []);
  const [categories, setCategories] = useState<string[]>(cached?.categories ?? []);
  const [loading, setLoading] = useState(!cached);
  const [hasMore, setHasMore] = useState(Boolean(cached?.hasMore));
  const [error, setError] = useState<string | null>(null);
  const loadedCount = useRef(cached?.rows.length ?? 0);
  const { refreshing } = useFinanceBackgroundLiveRefresh(user);

  const load = useCallback(
    async (append = false) => {
      if (!enabled) return;
      setError(null);
      try {
        const params = new URLSearchParams();
        if (filter === "personal" || filter === "business") {
          params.set("scope", filter);
        } else if (filter !== "all") {
          params.set("filter", filter);
        }
        if (q.trim()) params.set("q", q.trim());
        params.set("limit", String(FINANCE_TXN_PAGE_SIZE));
        params.set("offset", String(append ? loadedCount.current : 0));
        const [data, cats] = await Promise.all([
          apiClient.get<FinanceTxn[]>(`/finance/transactions?${params}`),
          apiClient.get<Array<{ parent: string }>>("/finance/categories"),
        ]);
        setRows((prev) => (append ? [...prev, ...data] : data));
        loadedCount.current = append ? loadedCount.current + data.length : data.length;
        const nextHasMore = data.length === FINANCE_TXN_PAGE_SIZE;
        setHasMore(nextHasMore);
        const nextCategories = [...new Set(cats.map((item) => item.parent).filter(Boolean))];
        setCategories(nextCategories);
        if (!append && filter === "all" && !q.trim()) {
          writeLastTxns({
            filter,
            q: "",
            rows: data,
            categories: nextCategories,
            hasMore: nextHasMore,
          });
        }
        notifyFinanceOverviewReady();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load transactions");
      } finally {
        setLoading(false);
      }
    },
    [enabled, filter, q],
  );

  useEffect(() => {
    if (!enabled) return;
    const next = readLastTxns(filter, q.trim());
    setRows(next?.rows ?? []);
    setCategories(next?.categories ?? []);
    setHasMore(Boolean(next?.hasMore));
    loadedCount.current = next?.rows.length ?? 0;
    setLoading(!next);
  }, [enabled, filter, q]);

  useFinanceReload(() => load(false), enabled);

  return {
    rows,
    categories,
    loading,
    refreshing,
    error,
    hasMore,
    loadMore: () => load(true),
    reload: () => load(false),
    setError,
  };
}
