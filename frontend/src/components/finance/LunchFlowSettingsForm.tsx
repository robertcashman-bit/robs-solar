"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import {
  integrationConnectionLabel,
  lunchFlowConfigStatusSchema,
  lunchFlowSyncResultSchema,
} from "@/lib/finance-schemas";
import { canWrite } from "@/lib/permissions";

const LUNCH_FLOW_DASHBOARD = "https://lunchflow.app/dashboard";

type LunchFlowSettingsFormProps = {
  onSaved?: () => void;
  readOnly?: boolean;
};

export function LunchFlowSettingsForm({ onSaved, readOnly = false }: LunchFlowSettingsFormProps) {
  const { user } = useAuth();
  const writable = canWrite(user) && !readOnly;

  const [apiKey, setApiKey] = useState("");
  const [configured, setConfigured] = useState(false);
  const [connectionState, setConnectionState] = useState<string | undefined>();
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
      setConnectionState(status.connection_state);
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
      setConnectionState(status.connection_state);
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
      const result = await apiClient.post<{ accounts: number; hint?: string }>(
        "/finance/integrations/lunch-flow/test",
      );
      if (result.accounts === 0) {
        setMessage(
          result.hint ??
            "Connected — 0 account(s) found. Enable them under Destinations → API → Account Access.",
        );
      } else {
        setMessage(`Connected — ${result.accounts} account(s) found in Lunch Flow.`);
      }
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
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Lunch Flow — personal banks</h2>
        <span
          className={`rounded-full px-3 py-1 text-xs font-medium ${
            connectionState === "active"
              ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
              : configured
                ? "bg-sky-500/15 text-sky-800 dark:text-sky-200"
                : "bg-amber-500/15 text-amber-800 dark:text-amber-200"
          }`}
        >
          {integrationConnectionLabel(connectionState, configured)}
        </span>
      </div>
      <p className="mt-2 text-sm text-[var(--muted)]">
        Authorise Lloyds, MBNA and Virgin Money in your browser at Lunch Flow, then sync balances
        here. Bank login happens on lunchflow.app (not in this app).
      </p>

      <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-sm text-[var(--muted)]">
        <li>
          Open Lunch Flow and connect each bank under <strong>Connections</strong> (complete the
          bank login screens in that tab).
        </li>
        <li>
          Create or open an <strong>API</strong> destination (Destinations → Add → API) and copy the
          API key.
        </li>
        <li>
          On that destination → <strong>Account Access</strong>, enable every account you want
          visible here.
        </li>
        <li>Paste the key below (if not already saved), then press <strong>Sync all</strong>.</li>
      </ol>

      {writable ? (
        <div className="mt-4 flex flex-wrap gap-2">
          <a
            href={LUNCH_FLOW_DASHBOARD}
            target="_blank"
            rel="noreferrer"
            className="solar-btn-primary text-sm"
          >
            Authorize banks at Lunch Flow
          </a>
          {configured ? (
            <button
              type="button"
              className="solar-btn-secondary text-sm"
              disabled={busy}
              onClick={() => void syncNow()}
            >
              Sync all
            </button>
          ) : null}
        </div>
      ) : null}

      {configured ? (
        <p className="mt-3 text-sm text-emerald-800 dark:text-emerald-200">
          API key saved{lastSyncAt ? ` — last synced ${lastSyncAt}` : ""}.
        </p>
      ) : (
        <p className="mt-3 text-sm text-amber-900 dark:text-amber-100">
          No API key saved yet — paste it below after creating the Lunch Flow API destination.
        </p>
      )}

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
          </div>
        </div>
      ) : null}
    </section>
  );
}
