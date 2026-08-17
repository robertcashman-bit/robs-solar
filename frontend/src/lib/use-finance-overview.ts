"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { FINANCE_CHANGED_EVENT, notifyFinanceOverviewReady } from "@/lib/finance-events";
import { financeOverviewSchema, type FinanceOverview } from "@/lib/finance-schemas";
import { currentMonthKey } from "@/lib/money";
import type { UserInfo } from "@/lib/schemas";
import { useFinanceBackgroundLiveRefresh } from "@/lib/use-finance-background-live-refresh";

const LAST_OVERVIEW_KEY = "robs-finance-last-overview";

function readLastOverview(): FinanceOverview | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(LAST_OVERVIEW_KEY);
    if (!raw) return null;
    return financeOverviewSchema.parse(JSON.parse(raw));
  } catch {
    return null;
  }
}

function writeLastOverview(overview: FinanceOverview): void {
  try {
    window.localStorage.setItem(LAST_OVERVIEW_KEY, JSON.stringify(overview));
  } catch {
    // ignore private mode / quota
  }
}

export function useFinanceOverview(user: UserInfo | null | undefined) {
  const enabled = Boolean(user);
  const cached = enabled ? readLastOverview() : null;
  const [overview, setOverview] = useState<FinanceOverview | null>(cached);
  const [loading, setLoading] = useState(!cached);
  const [error, setError] = useState<string | null>(null);
  const { refreshing: backgroundRefreshing } = useFinanceBackgroundLiveRefresh(user);
  const [manualRefreshing, setManualRefreshing] = useState(false);
  const overviewRef = useRef<FinanceOverview | null>(cached);

  const refresh = useCallback(
    async (opts?: { live?: boolean; fresh?: boolean }) => {
      if (!enabled) {
        return;
      }
      const live = Boolean(opts?.live);
      const fresh = Boolean(opts?.fresh);
      if (live) {
        setManualRefreshing(true);
      } else if (!overviewRef.current) {
        setLoading(true);
      }
      setError(null);
      try {
        const month = currentMonthKey();
        const params = new URLSearchParams({ month });
        if (live) params.set("live", "1");
        if (fresh) params.set("fresh", "1");
        const data = await apiClient.get<unknown>(`/finance/overview?${params.toString()}`);
        const parsed = financeOverviewSchema.parse(data);
        overviewRef.current = parsed;
        setOverview(parsed);
        writeLastOverview(parsed);
        notifyFinanceOverviewReady();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load finance overview");
      } finally {
        setLoading(false);
        setManualRefreshing(false);
      }
    },
    [enabled],
  );

  useEffect(() => {
    if (!enabled) return;
    const timer = window.setTimeout(() => void refresh(), 0);
    const onChanged = () => {
      void refresh({ fresh: true });
    };
    window.addEventListener(FINANCE_CHANGED_EVENT, onChanged);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener(FINANCE_CHANGED_EVENT, onChanged);
    };
  }, [enabled, refresh]);

  return {
    overview,
    loading,
    refreshing: backgroundRefreshing || manualRefreshing,
    error,
    refresh: () => refresh({ live: true }),
    reload: () => refresh({ fresh: true }),
  };
}
