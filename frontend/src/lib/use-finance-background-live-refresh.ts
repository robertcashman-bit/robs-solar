"use client";

import { useEffect, useRef, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { FINANCE_OVERVIEW_READY_EVENT, notifyFinanceChanged } from "@/lib/finance-events";
import { canWrite } from "@/lib/permissions";
import type { UserInfo } from "@/lib/schemas";

const COOLDOWN_KEY = "robs-finance-live-refresh-at";
const COOLDOWN_MS = 15 * 60 * 1000;
const FALLBACK_MS = 1800;

function withinCooldown(): boolean {
  try {
    const raw = window.sessionStorage.getItem(COOLDOWN_KEY);
    if (!raw) return false;
    const at = Number(raw);
    if (!Number.isFinite(at)) return false;
    return Date.now() - at < COOLDOWN_MS;
  } catch {
    return false;
  }
}

function markRefreshed(): void {
  try {
    window.sessionStorage.setItem(COOLDOWN_KEY, String(Date.now()));
  } catch {
    // ignore private mode
  }
}

/**
 * After stored figures paint, refresh live balances once per session window.
 * Waits for the dashboard GET (or a short fallback) so SQLite is not locked
 * by QuickFile / Lunch Flow during first paint.
 */
export function useFinanceBackgroundLiveRefresh(user: UserInfo | null | undefined) {
  const enabled = Boolean(user) && canWrite(user ?? null);
  const [refreshing, setRefreshing] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    if (!enabled) {
      started.current = false;
      return;
    }
    if (started.current || withinCooldown()) {
      return;
    }

    let cancelled = false;

    const run = () => {
      if (cancelled || started.current || withinCooldown()) {
        return;
      }
      started.current = true;
      void (async () => {
        setRefreshing(true);
        try {
          await apiClient.post("/finance/live-refresh", {});
          markRefreshed();
          notifyFinanceChanged();
        } catch {
          // Stored figures already shown.
        } finally {
          if (!cancelled) {
            setRefreshing(false);
          }
        }
      })();
    };

    const onReady = () => run();
    window.addEventListener(FINANCE_OVERVIEW_READY_EVENT, onReady);
    const timer = window.setTimeout(run, FALLBACK_MS);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      window.removeEventListener(FINANCE_OVERVIEW_READY_EVENT, onReady);
    };
  }, [enabled]);

  return { refreshing };
}
