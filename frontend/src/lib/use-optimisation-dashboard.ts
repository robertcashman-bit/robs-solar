"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import {
  recommendationsResponseSchema,
  systemWarningsResponseSchema,
  type OptimisationRecommendation,
  type SystemWarningsResponse,
} from "@/lib/schemas";

type UseOptimisationDashboardOptions = {
  enabled?: boolean;
};

export function useOptimisationDashboard({ enabled = true }: UseOptimisationDashboardOptions = {}) {
  const [warnings, setWarnings] = useState<SystemWarningsResponse | null>(null);
  const [recommendations, setRecommendations] = useState<OptimisationRecommendation[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    try {
      const [warnData, recData] = await Promise.all([
        apiClient.get("/metrics/warnings"),
        apiClient.get("/recommendations"),
      ]);
      setWarnings(systemWarningsResponseSchema.parse(warnData));
      setRecommendations(recommendationsResponseSchema.parse(recData).recommendations);
    } catch {
      setWarnings(null);
      setRecommendations([]);
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;
    const timer = window.setTimeout(() => void refresh(), 0);
    const poll = window.setInterval(() => void refresh(), 60_000);
    return () => {
      window.clearTimeout(timer);
      window.clearInterval(poll);
    };
  }, [enabled, refresh]);

  return { warnings, recommendations, loading, refresh };
}
