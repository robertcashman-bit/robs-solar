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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchOnce = useCallback(async () => {
    if (!enabled) {
      return;
    }
    setLoading(true);
    try {
      const data = octopusMeterPowerSchema.parse(await apiClient.get("/octopus/meter-power"));
      setMeter(data);
      setError(data.configured === false ? data.message || "Octopus not configured" : null);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load smart meter");
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    void fetchOnce();
    const timer = window.setInterval(() => void fetchOnce(), pollIntervalMs);
    return () => window.clearInterval(timer);
  }, [enabled, fetchOnce, pollIntervalMs]);

  return { meter, loading, error, refresh: fetchOnce };
}
