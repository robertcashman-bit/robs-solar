"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, apiClient } from "@/lib/api-client";
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

type FetchedOverview = {
  key: string;
  overview: FinanceOverview;
};

type FetchMeta = {
  key: string;
  status: "loading" | "ready" | "error";
  error: string | null;
};

function periodKey(personalPeriod: string, businessPeriod: string): string {
  return `${personalPeriod}|${businessPeriod}`;
}

function readLastOverview(
  _personalPeriod: string,
  _businessPeriod: string,
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
      // Always paint last saved hero + columns. Period money-in/out refreshes
      // from the network; snapshot cash/debts stay valid across lookbacks.
      return financeOverviewSchema.parse(parsed.data);
    }
    return financeOverviewSchema.parse(parsed);
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
  const key = periodKey(personalPeriod, businessPeriod);
  const cached = enabled
    ? readLastOverview(personalPeriod, businessPeriod)
    : null;

  const [fetched, setFetched] = useState<FetchedOverview | null>(null);
  const [fetchMeta, setFetchMeta] = useState<FetchMeta | null>(null);
  const { refreshing: backgroundRefreshing } =
    useFinanceBackgroundLiveRefresh(user);
  const [manualRefreshing, setManualRefreshing] = useState(false);
  const overviewRef = useRef<FinanceOverview | null>(null);
  const requestIdRef = useRef(0);

  const overview =
    fetched?.key === key ? fetched.overview : cached;
  const meta = fetchMeta?.key === key ? fetchMeta : null;
  const error = meta?.error ?? null;
  const loading = Boolean(
    enabled && !overview && meta?.status !== "error" && meta?.status !== "ready",
  );

  useEffect(() => {
    overviewRef.current = overview;
  }, [overview]);

  const refresh = useCallback(
    async (refreshOpts?: { live?: boolean; fresh?: boolean }) => {
      if (!enabled) {
        return;
      }
      const requestId = ++requestIdRef.current;
      const requestedPersonal = personalPeriod;
      const requestedBusiness = businessPeriod;
      const requestedKey = periodKey(requestedPersonal, requestedBusiness);
      const cacheEpoch = financeCacheWriteEpoch();
      const live = Boolean(refreshOpts?.live);
      const fresh = Boolean(refreshOpts?.fresh);
      if (live) {
        setManualRefreshing(true);
      } else if (!overviewRef.current) {
        setFetchMeta({ key: requestedKey, status: "loading", error: null });
      }
      try {
        // Manual Refresh: never block painting on QuickFile/Lunch Flow.
        // Race a short live sync, then always GET stored overview (?fresh=1).
        let liveWarning: string | null = null;
        if (live) {
          let timeoutId = 0;
          const livePost = apiClient.post("/finance/live-refresh", {});
          // Losing side of the race must not surface as unhandledrejection.
          void livePost.catch(() => undefined);
          try {
            await Promise.race([
              livePost,
              new Promise<never>((_, reject) => {
                timeoutId = window.setTimeout(() => {
                  reject(
                    new Error(
                      "Live sync is taking too long — showing stored figures.",
                    ),
                  );
                }, 8_000);
              }),
            ]);
          } catch (err) {
            liveWarning =
              err instanceof Error
                ? err.message
                : "Live refresh did not finish";
          } finally {
            window.clearTimeout(timeoutId);
          }
        }
        const month = currentMonthKey();
        const params = new URLSearchParams({ month });
        params.set("personal_period", requestedPersonal);
        params.set("business_period", requestedBusiness);
        if (live || fresh) params.set("fresh", "1");
        const data = await apiClient.get<unknown>(
          `/finance/overview?${params.toString()}`,
        );
        const parsed = financeOverviewSchema.parse(data);
        if (
          requestId !== requestIdRef.current ||
          !isFinanceCacheWriteCurrent(cacheEpoch)
        ) {
          return;
        }
        overviewRef.current = parsed;
        setFetched({ key: requestedKey, overview: parsed });
        setFetchMeta({
          key: requestedKey,
          status: liveWarning ? "error" : "ready",
          error: liveWarning,
        });
        writeLastOverview(parsed, requestedPersonal, requestedBusiness);
        notifyFinanceOverviewReady();
      } catch (err) {
        if (requestId !== requestIdRef.current) {
          return;
        }
        // Keep last-known figures on timeout / network blips — do not strand
        // the Overview on a dead error banner when local/server cache exists.
        const keepCached =
          Boolean(overviewRef.current)
          && err instanceof ApiError
          && (err.status === 504 || err.status === 503);
        if (keepCached && !live) {
          setFetchMeta({
            key: requestedKey,
            status: "ready",
            error: null,
          });
          return;
        }
        setFetchMeta({
          key: requestedKey,
          status: "error",
          error:
            err instanceof Error
              ? err.message
              : "Failed to load finance overview",
        });
      } finally {
        if (requestId === requestIdRef.current) {
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
