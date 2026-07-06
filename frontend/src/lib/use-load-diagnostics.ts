"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { loadDiagnosticsSchema, type LoadDiagnostics } from "@/lib/schemas";

type UseLoadDiagnosticsOptions = {
  enabled?: boolean;
  pollIntervalMs?: number;
};

export function useLoadDiagnostics({
  enabled = true,
  pollIntervalMs = 10000,
}: UseLoadDiagnosticsOptions = {}) {
  const [diagnostics, setDiagnostics] = useState<LoadDiagnostics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchOnce = useCallback(async () => {
    setLoading(true);
    try {
      const data = loadDiagnosticsSchema.parse(await apiClient.get("/metrics/diagnostics"));
      setDiagnostics(data);
      setError(null);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load diagnostics");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    void fetchOnce();
    const timer = window.setInterval(() => void fetchOnce(), pollIntervalMs);
    return () => window.clearInterval(timer);
  }, [enabled, fetchOnce, pollIntervalMs]);

  return { diagnostics, error, loading, refresh: fetchOnce };
}
