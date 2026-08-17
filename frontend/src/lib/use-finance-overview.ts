"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { FINANCE_CHANGED_EVENT } from "@/lib/finance-events";
import { financeOverviewSchema, type FinanceOverview } from "@/lib/finance-schemas";
import { currentMonthKey } from "@/lib/money";

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
      const data = await apiClient.get<unknown>(`/finance/overview?month=${currentMonthKey()}`);
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
    const onChanged = () => {
      void refresh();
    };
    window.addEventListener(FINANCE_CHANGED_EVENT, onChanged);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener(FINANCE_CHANGED_EVENT, onChanged);
    };
  }, [enabled, refresh]);

  return { overview, loading, error, refresh };
}
