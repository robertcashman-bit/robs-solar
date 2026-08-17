"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { FINANCE_CHANGED_EVENT } from "@/lib/finance-events";
import { financeOverviewSchema, type FinanceOverview } from "@/lib/finance-schemas";
import { currentMonthKey } from "@/lib/money";
import { canWrite } from "@/lib/permissions";
import type { UserInfo } from "@/lib/schemas";

export function useFinanceOverview(user: UserInfo | null | undefined) {
  const enabled = Boolean(user);
  const writable = canWrite(user ?? null);
  const [overview, setOverview] = useState<FinanceOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const liveStarted = useRef(false);

  const refresh = useCallback(
    async (opts?: { live?: boolean }) => {
      if (!enabled) {
        return;
      }
      const live = Boolean(opts?.live);
      if (live) {
        setRefreshing(true);
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
        setRefreshing(false);
      }
    },
    [enabled],
  );

  useEffect(() => {
    if (!enabled) return;
    liveStarted.current = false;
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

  useEffect(() => {
    if (!enabled || !writable || !overview || liveStarted.current) {
      return;
    }
    liveStarted.current = true;
    const timer = window.setTimeout(() => {
      void (async () => {
        try {
          await apiClient.post("/finance/live-refresh", {});
          await refresh();
        } catch {
          // Stored figures already shown; live refresh is best-effort.
        }
      })();
    }, 50);
    return () => window.clearTimeout(timer);
  }, [enabled, writable, overview, refresh]);

  return {
    overview,
    loading,
    refreshing,
    error,
    refresh: () => refresh({ live: true }),
  };
}
