"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { liveMetricsSchema, type LiveMetrics } from "@/lib/schemas";

function liveWebSocketUrl(): string {
  if (typeof window === "undefined") {
    return "";
  }
  // Hosted Vercel/Render proxies do not support WebSocket upgrades (404).
  const host = window.location.hostname;
  if (host !== "localhost" && host !== "127.0.0.1") {
    return "";
  }
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/backend";
  if (apiBase.startsWith("http")) {
    const url = new URL(apiBase);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = `${url.pathname.replace(/\/$/, "")}/ws/live`;
    url.search = "";
    url.hash = "";
    return url.toString();
  }
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}${apiBase.replace(/\/$/, "")}/ws/live`;
}

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
    let wsTimer: number | undefined;
    let usePolling = false;
    let stopped = false;

    const startPolling = () => {
      if (usePolling) {
        return;
      }
      usePolling = true;
      setConnected(false);
      void fetchOnce();
      pollTimer = window.setInterval(() => void fetchOnce(), pollIntervalMs);
    };

    // Always poll — hosted PWA cannot rely on WebSocket.
    startPolling();

    const wsUrl = liveWebSocketUrl();
    if (!wsUrl) {
      return () => {
        stopped = true;
        if (pollTimer) {
          window.clearInterval(pollTimer);
        }
      };
    }

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      wsTimer = window.setTimeout(() => {
        if (!stopped && ws.readyState !== WebSocket.OPEN) {
          ws.close();
        }
      }, 8000);

      ws.onopen = () => {
        window.clearTimeout(wsTimer);
        setConnected(true);
      };
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
      ws.onerror = () => ws.close();
      ws.onclose = () => setConnected(false);
    } catch {
      /* polling already running */
    }

    return () => {
      stopped = true;
      window.clearTimeout(wsTimer);
      if (pollTimer) {
        window.clearInterval(pollTimer);
      }
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [enabled, fetchOnce, pollIntervalMs]);

  return { metrics, error, connected, refresh: fetchOnce };
}
