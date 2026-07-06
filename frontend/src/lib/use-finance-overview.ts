"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { z } from "zod";

import {
  financeAccountSchema,
  financeLiabilitySchema,
  financeOverviewSchema,
  quickFileReportsSchema,
  type FinanceAccount,
  type FinanceLiability,
  type FinanceOverview,
  type QuickFileReports,
} from "@/lib/finance-schemas";

export function useFinanceOverview(enabled = true) {
  const [overview, setOverview] = useState<FinanceOverview | null>(null);
  const [quickfileReports, setQuickfileReports] = useState<QuickFileReports | null>(null);
  const [accounts, setAccounts] = useState<FinanceAccount[]>([]);
  const [liabilities, setLiabilities] = useState<FinanceLiability[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [overviewData, reportsData, accountsData, liabilitiesData] = await Promise.all([
        apiClient.get<unknown>("/finance/overview"),
        apiClient.get<unknown>("/finance/integrations/quickfile/reports"),
        apiClient.get<unknown>("/finance/accounts"),
        apiClient.get<unknown>("/finance/liabilities"),
      ]);
      setOverview(financeOverviewSchema.parse(overviewData));
      setQuickfileReports(quickFileReportsSchema.parse(reportsData));
      setAccounts(z.array(financeAccountSchema).parse(accountsData));
      setLiabilities(z.array(financeLiabilitySchema).parse(liabilitiesData));
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

  return { overview, quickfileReports, accounts, liabilities, loading, error, refresh };
}
