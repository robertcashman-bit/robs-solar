"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { notifyFinanceChanged } from "@/lib/finance-events";
import { formatUkDateTime } from "@/lib/finance-labels";
import { useAuth } from "@/lib/auth-context";
import {
  lunchFlowConfigStatusSchema,
  lunchFlowSyncResultSchema,
  type LunchFlowConfigStatus,
} from "@/lib/finance-schemas";

type LunchFlowSettingsPanelProps = {
  readOnly?: boolean;
  /** When provided by Connections, skip a duplicate status GET. */
  initialStatus?: LunchFlowConfigStatus | null;
  statusError?: string | null;
  /** Parent owns status loading (Connections page). */
  deferOwnStatusLoad?: boolean;
};

export function LunchFlowSettingsPanel({
  readOnly = false,
  initialStatus = null,
  statusError = null,
  deferOwnStatusLoad = false,
}: LunchFlowSettingsPanelProps) {
  const { user, loading: authLoading } = useAuth();
  const [status, setStatus] = useState<LunchFlowConfigStatus | null>(initialStatus);
  const [apiKey, setApiKey] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(statusError);
  const [busy, setBusy] = useState<"save" | "test" | "sync" | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(
    !deferOwnStatusLoad && initialStatus == null && statusError == null,
  );

  useEffect(() => {
    if (!initialStatus && !statusError && !deferOwnStatusLoad) {
      return;
    }
    const timer = window.setTimeout(() => {
      if (initialStatus) {
        setStatus(initialStatus);
        setError(null);
        setLoadingStatus(false);
      } else if (statusError) {
        setError(statusError);
        setLoadingStatus(false);
      } else if (deferOwnStatusLoad) {
        setLoadingStatus(true);
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [initialStatus, statusError, deferOwnStatusLoad]);

  const load = useCallback(async () => {
    if (!user) return;
    setLoadingStatus(true);
    try {
      const data = await apiClient.get<unknown>("/finance/integrations/lunchflow/status");
      setStatus(lunchFlowConfigStatusSchema.parse(data));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Lunch Flow status");
    } finally {
      setLoadingStatus(false);
    }
  }, [user]);

  useEffect(() => {
    if (deferOwnStatusLoad) return;
    // Cached user is enough; do not wait for authResolved (timeout/5xx leave it false).
    if (authLoading || !user) {
      if (!authLoading && !user) {
        queueMicrotask(() => setLoadingStatus(false));
      }
      return;
    }
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [authLoading, user, load, deferOwnStatusLoad]);

  async function save() {
    if (readOnly || busy) return;
    setBusy("save");
    try {
      const data = await apiClient.put<unknown>("/finance/integrations/lunchflow/settings", {
        api_key: apiKey,
      });
      setStatus(lunchFlowConfigStatusSchema.parse(data));
      setApiKey("");
      setMessage("Lunch Flow API key saved.");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the Lunch Flow key.");
    } finally {
      setBusy(null);
    }
  }

  async function testConnection() {
    if (readOnly || busy) return;
    setBusy("test");
    try {
      const data = await apiClient.post<{ ok?: boolean; account_count?: number }>(
        "/finance/integrations/lunchflow/test",
        {},
      );
      setMessage(`Lunch Flow connected. ${data.account_count ?? 0} account(s) visible.`);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lunch Flow test failed.");
    } finally {
      setBusy(null);
    }
  }

  async function sync() {
    if (readOnly || busy) return;
    setBusy("sync");
    try {
      const data = await apiClient.post<unknown>("/finance/integrations/lunchflow/sync", {});
      const parsed = lunchFlowSyncResultSchema.parse(data);
      setMessage(parsed.message);
      notifyFinanceChanged();
      setError(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lunch Flow sync failed.");
    } finally {
      setBusy(null);
    }
  }

  const statusLabel = loadingStatus
    ? "Loading status…"
    : status
      ? `${status.connected ? "Connected" : status.configured ? "Key saved" : "Not configured"}${
          status.last_sync_at ? ` · last sync ${formatUkDateTime(status.last_sync_at)}` : ""
        }`
      : error
        ? "Status unavailable"
        : "Not configured";

  return (
    <section className="solar-card space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">Lunch Flow</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Live personal and business bank balances via Lunch Flow (the app that already holds
            your bank connections). In Lunch Flow: Destinations → API → copy the key, then
            Save / Test / Sync here.
          </p>
        </div>
        {error || (!loadingStatus && !status) ? (
          <button
            type="button"
            className="solar-btn-ghost text-xs"
            onClick={() => void load()}
            disabled={loadingStatus || busy != null || !user}
          >
            {loadingStatus ? "Retrying…" : "Retry status"}
          </button>
        ) : null}
      </div>
      <p className="text-sm text-[var(--muted)]">{statusLabel}</p>
      {message ? <p className="text-sm text-emerald-700 dark:text-emerald-400">{message}</p> : null}
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
      <label className="block space-y-1 text-sm">
        <span>API key</span>
        <input
          className="solar-input"
          type="password"
          value={apiKey}
          onChange={(event) => setApiKey(event.target.value)}
          disabled={readOnly}
          placeholder={status?.api_key_set ? "Key saved — paste a new one to replace" : "lf_…"}
        />
      </label>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="solar-btn-primary" onClick={() => void save()} disabled={readOnly || busy != null}>
          {busy === "save" ? "Saving…" : "Save key"}
        </button>
        <button type="button" className="solar-btn-ghost" onClick={() => void testConnection()} disabled={readOnly || busy != null}>
          {busy === "test" ? "Testing…" : "Test"}
        </button>
        <button type="button" className="solar-btn-ghost" onClick={() => void sync()} disabled={readOnly || busy != null}>
          {busy === "sync" ? "Syncing…" : "Sync accounts"}
        </button>
      </div>
    </section>
  );
}
