"use client";

import { useCallback, useState } from "react";

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

type FetchedTxns = {
  key: string;
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
  const trimmedQ = q.trim();
  const cacheKey = `${filter}|${trimmedQ}`;
  const cached = enabled ? readLastTxns(filter, trimmedQ) : null;
  const [fetched, setFetched] = useState<FetchedTxns | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { refreshing } = useFinanceBackgroundLiveRefresh(user);

  const fromFetch = fetched?.key === cacheKey ? fetched : null;
  const active = fromFetch
    ?? (cached
      ? {
          key: cacheKey,
          rows: cached.rows,
          categories: cached.categories,
          hasMore: cached.hasMore,
        }
      : null);
  const rows = active?.rows ?? [];
  const categories = active?.categories ?? [];
  const hasMore = Boolean(active?.hasMore);
  const loading = Boolean(enabled && !active);

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
        if (trimmedQ) params.set("q", trimmedQ);
        params.set("limit", String(FINANCE_TXN_PAGE_SIZE));
        const offset = append && fetched?.key === cacheKey ? fetched.rows.length : 0;
        params.set("offset", String(offset));
        const [data, cats] = await Promise.all([
          apiClient.get<FinanceTxn[]>(`/finance/transactions?${params}`),
          apiClient.get<Array<{ parent: string }>>("/finance/categories"),
        ]);
        const nextCategories = [...new Set(cats.map((item) => item.parent).filter(Boolean))];
        const nextHasMore = data.length === FINANCE_TXN_PAGE_SIZE;
        const nextRows =
          append && fetched?.key === cacheKey ? [...fetched.rows, ...data] : data;
        setFetched({
          key: cacheKey,
          rows: nextRows,
          categories: nextCategories,
          hasMore: nextHasMore,
        });
        if (!append && filter === "all" && !trimmedQ) {
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
      }
    },
    [enabled, filter, trimmedQ, cacheKey, fetched],
  );

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
