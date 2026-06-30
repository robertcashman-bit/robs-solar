"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { liveMetricsSchema, type LiveMetrics } from "@/lib/schemas";

const WS_URL =
  typeof window !== "undefined"
    ? `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.hostname}:8000/ws/live`
    : "";

type UseLiveMetricsOptions = {
  enabled?: boolean;
  pollIntervalMs?: number;
};

export function useLiveMetrics({ enabled = true, pollIntervalMs = 5000 }: UseLiveMetricsOptions = {}) {
  const [metrics, setMetrics] = useState<LiveMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const fetchOnce = useCallback(async () => {
    try {
      const data = liveMetricsSchema.parse(await apiClient.get("/metrics/live"));
      setMetrics(data);
      setError(null);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load metrics");
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    let pollTimer: number | undefined;
    let usePolling = false;

    const startPolling = () => {
      usePolling = true;
      setConnected(false);
      void fetchOnce();
      pollTimer = window.setInterval(() => void fetchOnce(), pollIntervalMs);
    };

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(String(event.data)) as unknown;
          if (payload && typeof payload === "object" && "error" in payload) {
            setError(String((payload as { error: string }).error));
            return;
          }
          setMetrics(liveMetricsSchema.parse(payload));
          setError(null);
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onerror = () => {
        if (!usePolling) {
          ws.close();
          startPolling();
        }
      };
      ws.onclose = () => {
        setConnected(false);
        if (!usePolling) {
          startPolling();
        }
      };
    } catch {
      startPolling();
    }

    return () => {
      if (pollTimer) {
        window.clearInterval(pollTimer);
      }
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [enabled, fetchOnce, pollIntervalMs]);

  return { metrics, error, connected, refresh: fetchOnce };
}
