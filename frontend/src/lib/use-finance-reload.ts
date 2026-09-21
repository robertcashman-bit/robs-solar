"use client";

import { useEffect } from "react";

import { FINANCE_CHANGED_EVENT } from "@/lib/finance-events";

export function useFinanceReload(
  load: () => void | Promise<void>,
  enabled = true,
  initialDelayMs = 0,
) {
  useEffect(() => {
    if (!enabled) return;
    const timer = window.setTimeout(() => void load(), Math.max(0, initialDelayMs));
    const onChanged = () => {
      void load();
    };
    window.addEventListener(FINANCE_CHANGED_EVENT, onChanged);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener(FINANCE_CHANGED_EVENT, onChanged);
    };
  }, [enabled, load, initialDelayMs]);
}
