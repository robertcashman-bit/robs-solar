"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { octopusMeterPowerSchema, type OctopusMeterPower } from "@/lib/schemas";

type UseOctopusMeterOptions = {
  enabled?: boolean;
  pollIntervalMs?: number;
};

export function useOctopusMeter({
  enabled = true,
  pollIntervalMs = 30_000,
}: UseOctopusMeterOptions = {}) {
  const [meter, setMeter] = useState<OctopusMeterPower | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const loading = enabled && (refreshing || (meter === null && error === null));

  const fetchOnce = useCallback(async () => {
    if (!enabled) {
      return;
    }
    setRefreshing(true);
    try {
      const data = octopusMeterPowerSchema.parse(await apiClient.get("/octopus/meter-power"));
      setMeter(data);
      setError(data.configured === false ? data.message || "Octopus not configured" : null);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load smart meter");
    } finally {
      setRefreshing(false);
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    let pollTimer: number | undefined;
    const bootTimer = window.setTimeout(() => {
      void fetchOnce();
      pollTimer = window.setInterval(() => void fetchOnce(), pollIntervalMs);
    }, 0);
    return () => {
      window.clearTimeout(bootTimer);
      if (pollTimer) {
        window.clearInterval(pollTimer);
      }
    };
  }, [enabled, fetchOnce, pollIntervalMs]);

  return { meter, loading, error, refresh: fetchOnce };
}
