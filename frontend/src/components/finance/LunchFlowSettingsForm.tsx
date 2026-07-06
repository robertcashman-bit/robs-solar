"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import {
  lunchFlowConfigStatusSchema,
  lunchFlowSyncResultSchema,
} from "@/lib/finance-schemas";
import { canWrite } from "@/lib/permissions";

type LunchFlowSettingsFormProps = {
  onSaved?: () => void;
  readOnly?: boolean;
};

export function LunchFlowSettingsForm({ onSaved, readOnly = false }: LunchFlowSettingsFormProps) {
  const { user } = useAuth();
  const writable = canWrite(user) && !readOnly;

  const [apiKey, setApiKey] = useState("");
  const [configured, setConfigured] = useState(false);
  const [lastSyncAt, setLastSyncAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const data = await apiClient.get<unknown>("/finance/integrations/lunch-flow/status");
      const status = lunchFlowConfigStatusSchema.parse(data);
      setConfigured(status.configured);
      setLastSyncAt(status.last_sync_at ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load Lunch Flow settings");
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void load();
  }, [load]);

  async function save() {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const data = await apiClient.put<unknown>("/finance/integrations/lunch-flow/settings", {
        api_key: apiKey,
      });
      const status = lunchFlowConfigStatusSchema.parse(data);
      setConfigured(status.configured);
      setApiKey("");
      setMessage("Lunch Flow API key saved.");
      onSaved?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save API key");
    } finally {
      setBusy(false);
    }
  }

  async function testConnection() {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const result = await apiClient.post<{ accounts: number }>(
        "/finance/integrations/lunch-flow/test",
      );
      setMessage(`Connected — ${result.accounts} account(s) found in Lunch Flow.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connection test failed");
    } finally {
      setBusy(false);
    }
  }

  async function syncNow() {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const data = await apiClient.post<unknown>("/finance/integrations/lunch-flow/sync");
      const result = lunchFlowSyncResultSchema.parse(data);
      setMessage(result.message);
      await load();
      onSaved?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-[var(--muted)]">Loading Lunch Flow settings…</p>;
  }

  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--surface-sunken)]/30 p-5">
      <h2 className="text-lg font-semibold">Lunch Flow — personal banks</h2>
      <p className="mt-2 text-sm text-[var(--muted)]">
        Connect Lloyds, MBNA and Virgin Money at{" "}
        <a href="https://lunchflow.app/dashboard" target="_blank" rel="noreferrer" className="underline">
          lunchflow.app
        </a>
        , then paste your API key here. Balances and transactions sync automatically every day (~£2.50/mo,
        7-day free trial).
      </p>

      <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm text-[var(--muted)]">
        <li>
          Start your trial at{" "}
          <a href="https://lunchflow.app" target="_blank" rel="noreferrer" className="underline">
            lunchflow.app
          </a>
        </li>
        <li>Connect Lloyds, MBNA and Virgin Money under Connections</li>
        <li>
          Add an API destination (Destinations → Add → API) and copy the API key
        </li>
        <li>Paste the key below, then press Sync now on each bank card</li>
      </ol>

      {configured ? (
        <p className="mt-3 text-sm text-emerald-800 dark:text-emerald-200">
          API key saved{lastSyncAt ? ` — last synced ${lastSyncAt}` : ""}.
        </p>
      ) : null}

      {message ? (
        <p className="mt-3 rounded-lg border border-emerald-300/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-900 dark:text-emerald-200">
          {message}
        </p>
      ) : null}

      {error ? (
        <p className="mt-3 rounded-lg border border-red-300/40 bg-red-500/10 px-3 py-2 text-sm text-red-800 dark:text-red-200">
          {error}
        </p>
      ) : null}

      {writable ? (
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="flex flex-1 flex-col gap-1 text-sm">
            <span className="font-medium">API key</span>
            <input
              type="password"
              className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
              placeholder={configured ? "Enter a new key to replace the saved one" : "Paste from Lunch Flow"}
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              autoComplete="off"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="solar-btn-primary text-sm"
              disabled={busy || (!apiKey && !configured)}
              onClick={() => void save()}
            >
              Save key
            </button>
            <button
              type="button"
              className="solar-btn-secondary text-sm"
              disabled={busy || !configured}
              onClick={() => void testConnection()}
            >
              Test
            </button>
            <button
              type="button"
              className="solar-btn-secondary text-sm"
              disabled={busy || !configured}
              onClick={() => void syncNow()}
            >
              Sync all
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
