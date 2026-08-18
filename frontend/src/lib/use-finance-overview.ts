"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiClient } from "@/lib/api-client";
import {
  FINANCE_LAST_OVERVIEW_KEY,
  financeCacheWriteEpoch,
  isFinanceCacheWriteCurrent,
} from "@/lib/finance-local-cache";
import {
  FINANCE_CHANGED_EVENT,
  notifyFinanceOverviewReady,
} from "@/lib/finance-events";
import {
  financeOverviewSchema,
  type FinanceOverview,
} from "@/lib/finance-schemas";
import { currentMonthKey } from "@/lib/money";
import type { UserInfo } from "@/lib/schemas";
import { useFinanceBackgroundLiveRefresh } from "@/lib/use-finance-background-live-refresh";

const LAST_OVERVIEW_KEY = FINANCE_LAST_OVERVIEW_KEY;

type StoredOverview = {
  personalPeriod: string;
  businessPeriod: string;
  data: unknown;
};

function readLastOverview(
  personalPeriod: string,
  businessPeriod: string,
): FinanceOverview | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(LAST_OVERVIEW_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredOverview | FinanceOverview;
    if (
      parsed &&
      typeof parsed === "object" &&
      "data" in parsed &&
      "personalPeriod" in parsed &&
      "businessPeriod" in parsed
    ) {
      if (
        parsed.personalPeriod !== personalPeriod ||
        parsed.businessPeriod !== businessPeriod
      ) {
        return null;
      }
      return financeOverviewSchema.parse(parsed.data);
    }
    // Legacy unkeyed payload: only reuse for the default 1m/1m lookback.
    if (personalPeriod === "1m" && businessPeriod === "1m") {
      return financeOverviewSchema.parse(parsed);
    }
    return null;
  } catch {
    return null;
  }
}

function writeLastOverview(
  overview: FinanceOverview,
  personalPeriod: string,
  businessPeriod: string,
): void {
  try {
    const payload: StoredOverview = {
      personalPeriod,
      businessPeriod,
      data: overview,
    };
    window.localStorage.setItem(LAST_OVERVIEW_KEY, JSON.stringify(payload));
  } catch {
    // ignore private mode / quota
  }
}

export function useFinanceOverview(
  user: UserInfo | null | undefined,
  opts?: { personalPeriod?: string; businessPeriod?: string },
) {
  const enabled = Boolean(user);
  const personalPeriod = opts?.personalPeriod ?? "1m";
  const businessPeriod = opts?.businessPeriod ?? "1m";
  const cached = enabled
    ? readLastOverview(personalPeriod, businessPeriod)
    : null;
  const [overview, setOverview] = useState<FinanceOverview | null>(cached);
  const [loading, setLoading] = useState(!cached);
  const [error, setError] = useState<string | null>(null);
  const { refreshing: backgroundRefreshing } =
    useFinanceBackgroundLiveRefresh(user);
  const [manualRefreshing, setManualRefreshing] = useState(false);
  const overviewRef = useRef<FinanceOverview | null>(cached);
  const requestIdRef = useRef(0);
  const periodsRef = useRef({ personalPeriod, businessPeriod });
  periodsRef.current = { personalPeriod, businessPeriod };

  useEffect(() => {
    const next = enabled
      ? readLastOverview(personalPeriod, businessPeriod)
      : null;
    overviewRef.current = next;
    setOverview(next);
    setLoading(Boolean(enabled && !next));
  }, [enabled, personalPeriod, businessPeriod]);

  const refresh = useCallback(
    async (refreshOpts?: { live?: boolean; fresh?: boolean }) => {
      if (!enabled) {
        return;
      }
      const requestId = ++requestIdRef.current;
      const requestedPersonal = personalPeriod;
      const requestedBusiness = businessPeriod;
      const cacheEpoch = financeCacheWriteEpoch();
      const live = Boolean(refreshOpts?.live);
      const fresh = Boolean(refreshOpts?.fresh);
      if (live) {
        setManualRefreshing(true);
      } else if (!overviewRef.current) {
        setLoading(true);
      }
      setError(null);
      try {
        const month = currentMonthKey();
        const params = new URLSearchParams({ month });
        params.set("personal_period", requestedPersonal);
        params.set("business_period", requestedBusiness);
        if (live) params.set("live", "1");
        if (fresh) params.set("fresh", "1");
        const data = await apiClient.get<unknown>(
          `/finance/overview?${params.toString()}`,
        );
        const parsed = financeOverviewSchema.parse(data);
        if (
          requestId !== requestIdRef.current ||
          periodsRef.current.personalPeriod !== requestedPersonal ||
          periodsRef.current.businessPeriod !== requestedBusiness ||
          !isFinanceCacheWriteCurrent(cacheEpoch)
        ) {
          return;
        }
        overviewRef.current = parsed;
        setOverview(parsed);
        writeLastOverview(parsed, requestedPersonal, requestedBusiness);
        notifyFinanceOverviewReady();
      } catch (err) {
        if (requestId !== requestIdRef.current) {
          return;
        }
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load finance overview",
        );
      } finally {
        if (requestId === requestIdRef.current) {
          setLoading(false);
          setManualRefreshing(false);
        }
      }
    },
    [enabled, personalPeriod, businessPeriod],
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
