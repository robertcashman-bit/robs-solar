"use client";

import { useCallback, useState } from "react";

import { apiClient } from "@/lib/api-client";
import {
  FINANCE_LAST_TRANSACTIONS_KEY,
  financeCacheWriteEpoch,
  isFinanceCacheWriteCurrent,
} from "@/lib/finance-local-cache";
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

export type FinanceCategoryOption = {
  parent: string;
  scope: string;
};

export const FINANCE_TXN_PAGE_SIZE = 50;
const LAST_TXNS_KEY = FINANCE_LAST_TRANSACTIONS_KEY;

type CachedTxns = {
  filter: string;
  scope: string;
  q: string;
  dateFrom: string;
  dateTo: string;
  rows: FinanceTxn[];
  categories: string[];
  categoryOptions?: FinanceCategoryOption[];
  hasMore: boolean;
};

type FetchedTxns = {
  key: string;
  rows: FinanceTxn[];
  categories: string[];
  categoryOptions: FinanceCategoryOption[];
  hasMore: boolean;
};

function readLastTxns(
  filter: string,
  q: string,
  dateFrom: string,
  dateTo: string,
  scope: string,
): CachedTxns | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(LAST_TXNS_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CachedTxns;
    if (
      parsed.filter !== filter ||
      (parsed.scope || "both") !== scope ||
      parsed.q !== q ||
      (parsed.dateFrom || "") !== dateFrom ||
      (parsed.dateTo || "") !== dateTo
    ) {
      return null;
    }
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

function normalizeCategoryOptions(
  cats: Array<{ parent?: string; scope?: string }>,
): FinanceCategoryOption[] {
  return cats
    .map((item) => ({
      parent: String(item.parent || "").trim(),
      scope: String(item.scope || "").trim(),
    }))
    .filter((item) => item.parent);
}

export function useFinanceTransactions(
  user: UserInfo | null | undefined,
  filter: string,
  q: string,
  dateFrom?: string,
  dateTo?: string,
  scope?: string | null,
) {
  const enabled = Boolean(user);
  const trimmedQ = q.trim();
  const from = dateFrom ?? "";
  const to = dateTo ?? "";
  const scopeKey = scope && scope !== "both" ? scope : "both";
  const cacheKey = `${filter}|${scopeKey}|${trimmedQ}|${from}|${to}`;
  const cached = enabled
    ? readLastTxns(filter, trimmedQ, from, to, scopeKey)
    : null;
  const [fetched, setFetched] = useState<FetchedTxns | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { refreshing } = useFinanceBackgroundLiveRefresh(user);

  const fromFetch = fetched?.key === cacheKey ? fetched : null;
  const active =
    fromFetch ??
    (cached
      ? {
          key: cacheKey,
          rows: cached.rows,
          categories: cached.categories,
          categoryOptions:
            cached.categoryOptions ??
            cached.categories.map((parent) => ({ parent, scope: "" })),
          hasMore: cached.hasMore,
        }
      : null);
  const rows = active?.rows ?? [];
  const categories = active?.categories ?? [];
  const categoryOptions = active?.categoryOptions ?? [];
  const hasMore = Boolean(active?.hasMore);
  const loading = Boolean(enabled && !active);

  const load = useCallback(
    async (append = false) => {
      if (!enabled) return;
      const cacheEpoch = financeCacheWriteEpoch();
      setError(null);
      try {
        const params = new URLSearchParams();
        const catParams = new URLSearchParams();
        if (scopeKey === "personal" || scopeKey === "business") {
          params.set("scope", scopeKey);
          catParams.set("scope", scopeKey);
        } else if (filter === "personal" || filter === "business") {
          params.set("scope", filter);
          catParams.set("scope", filter);
        }
        if (
          filter !== "all" &&
          filter !== "personal" &&
          filter !== "business"
        ) {
          params.set("filter", filter);
        }
        if (trimmedQ) params.set("q", trimmedQ);
        if (from) params.set("date_from", from);
        if (to) params.set("date_to", to);
        params.set("limit", String(FINANCE_TXN_PAGE_SIZE));
        const offset =
          append && fetched?.key === cacheKey ? fetched.rows.length : 0;
        params.set("offset", String(offset));
        const categoriesPath = catParams.toString()
          ? `/finance/categories?${catParams}`
          : "/finance/categories";
        const [data, cats] = await Promise.all([
          apiClient.get<FinanceTxn[]>(`/finance/transactions?${params}`),
          apiClient.get<Array<{ parent: string; scope?: string }>>(categoriesPath),
        ]);
        if (!isFinanceCacheWriteCurrent(cacheEpoch)) {
          return;
        }
        const nextCategoryOptions = normalizeCategoryOptions(cats);
        const nextCategories = [
          ...new Set(nextCategoryOptions.map((item) => item.parent)),
        ];
        const nextHasMore = data.length === FINANCE_TXN_PAGE_SIZE;
        const nextRows =
          append && fetched?.key === cacheKey
            ? [...fetched.rows, ...data]
            : data;
        setFetched({
          key: cacheKey,
          rows: nextRows,
          categories: nextCategories,
          categoryOptions: nextCategoryOptions,
          hasMore: nextHasMore,
        });
        if (
          !append &&
          filter === "all" &&
          scopeKey === "both" &&
          !trimmedQ &&
          !from &&
          !to
        ) {
          writeLastTxns({
            filter,
            scope: scopeKey,
            q: "",
            dateFrom: "",
            dateTo: "",
            rows: data,
            categories: nextCategories,
            categoryOptions: nextCategoryOptions,
            hasMore: nextHasMore,
          });
        }
        notifyFinanceOverviewReady();
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load transactions",
        );
      }
    },
    [enabled, filter, scopeKey, trimmedQ, from, to, cacheKey, fetched],
  );

  const patchRow = useCallback(
    (txnId: number, patch: Partial<FinanceTxn>) => {
      setFetched((current) => {
        if (!current || current.key !== cacheKey) return current;
        return {
          ...current,
          rows: current.rows.map((row) =>
            row.id === txnId ? { ...row, ...patch } : row,
          ),
          categories:
            patch.category && !current.categories.includes(patch.category)
              ? [...current.categories, patch.category]
              : current.categories,
          categoryOptions:
            patch.category &&
            !current.categoryOptions.some(
              (item) =>
                item.parent === patch.category &&
                item.scope === String(patch.scope || ""),
            )
              ? [
                  ...current.categoryOptions,
                  {
                    parent: patch.category,
                    scope: String(patch.scope || ""),
                  },
                ]
              : current.categoryOptions,
        };
      });
    },
    [cacheKey],
  );

  useFinanceReload(() => load(false), enabled);

  return {
    rows,
    categories,
    categoryOptions,
    loading,
    refreshing,
    error,
    hasMore,
    loadMore: () => load(true),
    reload: () => load(false),
    patchRow,
    setError,
  };
}
