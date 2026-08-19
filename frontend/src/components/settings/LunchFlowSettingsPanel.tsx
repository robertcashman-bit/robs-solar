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
};

export function LunchFlowSettingsPanel({ readOnly = false }: LunchFlowSettingsPanelProps) {
  const { user } = useAuth();
  const [status, setStatus] = useState<LunchFlowConfigStatus | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"save" | "test" | "sync" | null>(null);

  const load = useCallback(async () => {
    if (!user) return;
    try {
      const data = await apiClient.get<unknown>("/finance/integrations/lunchflow/status");
      setStatus(lunchFlowConfigStatusSchema.parse(data));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Lunch Flow status");
    }
  }, [user]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

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

  return (
    <section className="solar-card space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Lunch Flow</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Live personal and business bank balances via Lunch Flow (the app that already holds
          your bank connections). TrueLayer Open Banking stays available above. In Lunch Flow:
          Destinations → API → copy the key, then Save / Test / Sync here.
        </p>
      </div>
      {status ? (
        <p className="text-sm text-[var(--muted)]">
          {status.connected ? "Connected" : status.configured ? "Key saved" : "Not configured"}
          {status.last_sync_at
            ? ` · last sync ${formatUkDateTime(status.last_sync_at)}`
            : ""}
        </p>
      ) : null}
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
