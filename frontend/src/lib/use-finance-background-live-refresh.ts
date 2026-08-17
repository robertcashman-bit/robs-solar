"use client";

import { useEffect, useRef, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { notifyFinanceChanged } from "@/lib/finance-events";
import { canWrite } from "@/lib/permissions";
import type { UserInfo } from "@/lib/schemas";

const COOLDOWN_KEY = "robs-finance-live-refresh-at";
const COOLDOWN_MS = 15 * 60 * 1000;

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
 * After stored Neon figures paint, refresh live balances once per session window.
 * Does not pull a year of transactions — that stays on explicit Refresh / Connect.
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
    started.current = true;
    const timer = window.setTimeout(() => {
      void (async () => {
        setRefreshing(true);
        try {
          await apiClient.post("/finance/live-refresh", {});
          markRefreshed();
          notifyFinanceChanged();
        } catch {
          // Stored figures already shown.
        } finally {
          setRefreshing(false);
        }
      })();
    }, 50);
    return () => window.clearTimeout(timer);
  }, [enabled]);

  return { refreshing };
}
