"use client";

import { useEffect } from "react";

import { FINANCE_CHANGED_EVENT } from "@/lib/finance-events";

export function useFinanceReload(load: () => void | Promise<void>, enabled = true) {
  useEffect(() => {
    if (!enabled) return;
    const timer = window.setTimeout(() => void load(), 0);
    const onChanged = () => {
      void load();
    };
    window.addEventListener(FINANCE_CHANGED_EVENT, onChanged);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener(FINANCE_CHANGED_EVENT, onChanged);
    };
  }, [enabled, load]);
}
