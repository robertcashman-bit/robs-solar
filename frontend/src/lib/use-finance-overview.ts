"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { financeOverviewSchema, type FinanceOverview } from "@/lib/finance-schemas";

export function useFinanceOverview(enabled = true) {
  const [overview, setOverview] = useState<FinanceOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<unknown>("/finance/overview");
      setOverview(financeOverviewSchema.parse(data));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load finance overview");
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;
    const timer = window.setTimeout(() => void refresh(), 0);
    return () => window.clearTimeout(timer);
  }, [enabled, refresh]);

  return { overview, loading, error, refresh };
}
