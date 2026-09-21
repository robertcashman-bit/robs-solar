"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import {
  fundingCircleConfigStatusSchema,
  lunchFlowConfigStatusSchema,
  quickFileConfigStatusSchema,
  type FundingCircleConfigStatus,
  type LunchFlowConfigStatus,
  type QuickFileConfigStatus,
} from "@/lib/finance-schemas";
import type { UserInfo } from "@/lib/schemas";

export type ConnectionStatuses = {
  lunchflow: LunchFlowConfigStatus;
  quickfile: QuickFileConfigStatus;
  funding_circle: FundingCircleConfigStatus;
};

/**
 * One GET for all Connections panels. Avoids three parallel status calls that
 * queue on a single serverless isolate and trip the client abort window.
 */
export function useConnectionStatuses(user: UserInfo | null | undefined): {
  statuses: ConnectionStatuses | null;
  error: string | null;
  loading: boolean;
  reload: () => Promise<void>;
} {
  const [statuses, setStatuses] = useState<ConnectionStatuses | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const reload = useCallback(async () => {
    if (!user) {
      setStatuses(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<unknown>("/finance/integrations/connection-status");
      if (!data || typeof data !== "object") {
        throw new Error("Unexpected connection status response");
      }
      const body = data as Record<string, unknown>;
      const lunchflow = lunchFlowConfigStatusSchema.parse(body.lunchflow);
      const quickfile = quickFileConfigStatusSchema.parse(body.quickfile);
      const funding_circle = fundingCircleConfigStatusSchema.parse(body.funding_circle);
      setStatuses({ lunchflow, quickfile, funding_circle });
    } catch (err) {
      setStatuses(null);
      setError(err instanceof Error ? err.message : "Failed to load connection status");
    } finally {
      setLoading(false);
    }
  }, [user]);

  // Cached session user is enough — do not wait for authResolved. /auth/me
  // timeout or 5xx intentionally leaves auth unresolved so Connections can
  // still paint; status GET does not need CSRF.
  useEffect(() => {
    if (!user) {
      return;
    }
    void reload();
  }, [user, reload]);

  return { statuses, error, loading, reload };
}
