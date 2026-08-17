"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { notifyFinanceChanged } from "@/lib/finance-events";
import { useAuth } from "@/lib/auth-context";
import {
  trueLayerConfigStatusSchema,
  trueLayerSyncResultSchema,
  type TrueLayerConfigStatus,
} from "@/lib/finance-schemas";

type OpenBankingSettingsPanelProps = {
  readOnly?: boolean;
};

export function OpenBankingSettingsPanel({ readOnly = false }: OpenBankingSettingsPanelProps) {
  const { user, loading: authLoading } = useAuth();
  const [status, setStatus] = useState<TrueLayerConfigStatus | null>(null);
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [redirectUri, setRedirectUri] = useState("");
  const [environment, setEnvironment] = useState("sandbox");
  const [secretSet, setSecretSet] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"save" | "connect" | "sync" | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);

  const load = useCallback(async () => {
    if (!user) return;
    setLoadingStatus(true);
    setError(null);
    try {
      const data = await apiClient.get<unknown>("/finance/integrations/open-banking/status");
      const parsed = trueLayerConfigStatusSchema.parse(data);
      setStatus(parsed);
      setClientId(parsed.client_id);
      setRedirectUri(parsed.redirect_uri);
      setEnvironment(parsed.environment);
      setSecretSet(parsed.client_secret_set);
    } catch (err) {
      setStatus(null);
      setError(err instanceof Error ? err.message : "Failed to load Open Banking status");
    } finally {
      setLoadingStatus(false);
    }
  }, [user]);

  useEffect(() => {
    if (authLoading) {
      return;
    }
    if (!user) {
      queueMicrotask(() => setLoadingStatus(false));
      return;
    }
    let active = true;
    void (async () => {
      setLoadingStatus(true);
      setError(null);
      try {
        const data = await apiClient.get<unknown>("/finance/integrations/open-banking/status");
        if (!active) return;
        const parsed = trueLayerConfigStatusSchema.parse(data);
        setStatus(parsed);
        setClientId(parsed.client_id);
        setRedirectUri(parsed.redirect_uri);
        setEnvironment(parsed.environment);
        setSecretSet(parsed.client_secret_set);
      } catch (err) {
        if (!active) return;
        setStatus(null);
        setError(err instanceof Error ? err.message : "Failed to load Open Banking status");
      } finally {
        if (active) setLoadingStatus(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [authLoading, user]);

  async function save() {
    setBusy("save");
    setError(null);
    setMessage(null);
    try {
      const data = await apiClient.put<unknown>("/finance/integrations/open-banking/settings", {
        client_id: clientId,
        client_secret: clientSecret || undefined,
        redirect_uri: redirectUri,
        environment,
      });
      const parsed = trueLayerConfigStatusSchema.parse(data);
      setStatus(parsed);
      setSecretSet(parsed.client_secret_set);
      setClientSecret("");
      setMessage("Open Banking settings saved");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(null);
    }
  }

  async function connect() {
    setBusy("connect");
    setError(null);
    try {
      const data = await apiClient.get<{ authorize_url: string }>(
        "/finance/integrations/open-banking/authorize",
      );
      window.location.href = data.authorize_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connect failed");
      setBusy(null);
    }
  }

  async function sync() {
    setBusy("sync");
    setError(null);
    setMessage(null);
    try {
      const data = await apiClient.post<unknown>("/finance/integrations/open-banking/sync");
      const parsed = trueLayerSyncResultSchema.parse(data);
      setMessage(parsed.message);
      notifyFinanceChanged();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setBusy(null);
    }
  }

  if (loadingStatus) {
    return <p className="text-sm text-[var(--muted)]">Loading Open Banking…</p>;
  }

  return (
    <section className="solar-card space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Open Banking (TrueLayer)</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          One-time TrueLayer credentials. After they are saved, use Log in to
          your bank and import — we pull accounts, cards, and Funding Circle.
        </p>
      </div>
      {error ? <p className="text-sm text-red-500">{error}</p> : null}
      {message ? <p className="text-sm text-emerald-500">{message}</p> : null}
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="space-y-1 text-sm">
          <span>Client ID</span>
          <input
            className="w-full rounded-lg border border-[var(--border)] bg-transparent px-3 py-2"
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            disabled={readOnly}
          />
        </label>
        <label className="space-y-1 text-sm">
          <span>Client secret {secretSet ? "(saved)" : ""}</span>
          <input
            type="password"
            className="w-full rounded-lg border border-[var(--border)] bg-transparent px-3 py-2"
            value={clientSecret}
            onChange={(e) => setClientSecret(e.target.value)}
            placeholder={secretSet ? "Leave blank to keep existing" : ""}
            disabled={readOnly}
          />
        </label>
        <label className="space-y-1 text-sm sm:col-span-2">
          <span>Redirect URI</span>
          <input
            className="w-full rounded-lg border border-[var(--border)] bg-transparent px-3 py-2"
            value={redirectUri}
            onChange={(e) => setRedirectUri(e.target.value)}
            placeholder="https://your-app/backend/finance/integrations/open-banking/callback"
            disabled={readOnly}
          />
        </label>
        <label className="space-y-1 text-sm">
          <span>Environment</span>
          <select
            className="w-full rounded-lg border border-[var(--border)] bg-transparent px-3 py-2"
            value={environment}
            onChange={(e) => setEnvironment(e.target.value)}
            disabled={readOnly}
          >
            <option value="sandbox">Sandbox</option>
            <option value="live">Live</option>
          </select>
        </label>
      </div>
      {!readOnly ? (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-lg bg-amber-500 px-4 py-2 text-sm font-medium text-slate-900"
            onClick={() => void save()}
            disabled={busy != null}
          >
            {busy === "save" ? "Saving…" : "Save"}
          </button>
          <button
            type="button"
            className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm"
            onClick={() => void connect()}
            disabled={busy != null || !status?.configured}
          >
            {busy === "connect" ? "Redirecting…" : "Log in to your bank"}
          </button>
          <button
            type="button"
            className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm"
            onClick={() => void sync()}
            disabled={busy != null || !status?.connected}
          >
            {busy === "sync" ? "Syncing…" : "Pull latest"}
          </button>
        </div>
      ) : null}
    </section>
  );
}
