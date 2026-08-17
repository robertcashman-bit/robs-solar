"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { FINANCE_CHANGED_EVENT } from "@/lib/finance-events";
import { financeOverviewSchema, type FinanceOverview } from "@/lib/finance-schemas";
import { currentMonthKey } from "@/lib/money";
import type { UserInfo } from "@/lib/schemas";
import { useFinanceBackgroundLiveRefresh } from "@/lib/use-finance-background-live-refresh";

export function useFinanceOverview(user: UserInfo | null | undefined) {
  const enabled = Boolean(user);
  const [overview, setOverview] = useState<FinanceOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { refreshing: backgroundRefreshing } = useFinanceBackgroundLiveRefresh(user);
  const [manualRefreshing, setManualRefreshing] = useState(false);

  const refresh = useCallback(
    async (opts?: { live?: boolean }) => {
      if (!enabled) {
        return;
      }
      const live = Boolean(opts?.live);
      if (live) {
        setManualRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);
      try {
        const month = currentMonthKey();
        const path = live
          ? `/finance/overview?month=${month}&live=1`
          : `/finance/overview?month=${month}`;
        const data = await apiClient.get<unknown>(path);
        setOverview(financeOverviewSchema.parse(data));
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
      void refresh();
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
  };
}
