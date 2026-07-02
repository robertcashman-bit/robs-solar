"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import {
  quickFileConfigStatusSchema,
  quickFileSyncResultSchema,
  type QuickFileConfigStatus,
} from "@/lib/finance-schemas";

type QuickFileSettingsPanelProps = {
  readOnly?: boolean;
};

export function QuickFileSettingsPanel({ readOnly = false }: QuickFileSettingsPanelProps) {
  const [status, setStatus] = useState<QuickFileConfigStatus | null>(null);
  const [accountNumber, setAccountNumber] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [applicationId, setApplicationId] = useState("");
  const [keyAlreadySet, setKeyAlreadySet] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"save" | "test" | "sync" | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await apiClient.get<unknown>("/finance/integrations/quickfile/status");
      const parsed = quickFileConfigStatusSchema.parse(data);
      setStatus(parsed);
      setAccountNumber(parsed.account_number);
      setApplicationId(parsed.application_id);
      setKeyAlreadySet(parsed.api_key_set);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load QuickFile status");
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function saveSettings() {
    setError(null);
    setMessage(null);
    setBusy("save");
    try {
      const data = await apiClient.put<unknown>("/finance/integrations/quickfile/settings", {
        account_number: accountNumber,
        api_key: apiKey,
        application_id: applicationId,
      });
      const parsed = quickFileConfigStatusSchema.parse(data);
      setStatus(parsed);
      setKeyAlreadySet(parsed.api_key_set);
      setApiKey("");
      setMessage("QuickFile settings saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(null);
    }
  }

  async function testConnection() {
    setError(null);
    setMessage(null);
    setBusy("test");
    try {
      if (!keyAlreadySet && !apiKey) {
        await saveSettings();
      }
      const result = await apiClient.post<{ ok?: boolean; sample_count?: number }>(
        "/finance/integrations/quickfile/test",
      );
      setMessage(
        result.ok
          ? `QuickFile connection OK (${result.sample_count ?? 0} sample client row).`
          : "QuickFile responded but connection check was inconclusive.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connection test failed");
    } finally {
      setBusy(null);
    }
  }

  async function syncNow() {
    setError(null);
    setMessage(null);
    setBusy("sync");
    try {
      const data = await apiClient.post<unknown>("/finance/integrations/quickfile/sync");
      const result = quickFileSyncResultSchema.parse(data);
      setMessage(result.message);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="solar-card space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">QuickFile</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Sync business bank balances and unpaid invoice debtors from QuickFile. Use the same
            account number, API key, and application ID as Custody Note.
          </p>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-xs font-medium ${
            status?.configured
              ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
              : "bg-amber-500/15 text-amber-800 dark:text-amber-200"
          }`}
        >
          {status?.configured ? "Configured" : "Not configured"}
        </span>
      </div>

      {status?.last_sync_at ? (
        <p className="text-xs text-[var(--muted)]">
          Last sync: {new Date(status.last_sync_at).toLocaleString("en-GB")}
        </p>
      ) : null}

      {error ? (
        <p className="rounded-lg border border-red-300/40 bg-red-500/10 px-3 py-2 text-sm text-red-800 dark:text-red-200">
          {error}
        </p>
      ) : null}
      {message ? (
        <p className="rounded-lg border border-emerald-300/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-900 dark:text-emerald-200">
          {message}
        </p>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="mb-1 block text-[var(--muted)]">Account number</span>
          <input
            className="solar-input w-full"
            value={accountNumber}
            onChange={(e) => setAccountNumber(e.target.value)}
            disabled={readOnly}
            autoComplete="off"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-[var(--muted)]">Application ID</span>
          <input
            className="solar-input w-full"
            value={applicationId}
            onChange={(e) => setApplicationId(e.target.value)}
            disabled={readOnly}
            autoComplete="off"
          />
        </label>
        <label className="block text-sm sm:col-span-2">
          <span className="mb-1 block text-[var(--muted)]">
            API key {keyAlreadySet ? "(leave blank to keep existing)" : ""}
          </span>
          <input
            className="solar-input w-full"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            disabled={readOnly}
            autoComplete="off"
          />
        </label>
      </div>

      {!readOnly ? (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="solar-btn-secondary"
            disabled={busy !== null}
            onClick={() => void saveSettings()}
          >
            {busy === "save" ? "Saving…" : "Save settings"}
          </button>
          <button
            type="button"
            className="solar-btn-secondary"
            disabled={busy !== null}
            onClick={() => void testConnection()}
          >
            {busy === "test" ? "Testing…" : "Test connection"}
          </button>
          <button
            type="button"
            className="solar-btn-primary"
            disabled={busy !== null}
            onClick={() => void syncNow()}
          >
            {busy === "sync" ? "Syncing…" : "Sync now"}
          </button>
        </div>
      ) : null}
    </section>
  );
}
