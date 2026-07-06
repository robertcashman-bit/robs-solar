"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { OpenBankingSetupInstructions } from "@/components/finance/OpenBankingSetupInstructions";
import { apiClient } from "@/lib/api-client";
import {
  openBankingConfigStatusSchema,
  openBankingTestResultSchema,
  type OpenBankingConfigStatus,
  type OpenBankingTestResult,
} from "@/lib/finance-schemas";

type OpenBankingSettingsFormProps = {
  readOnly?: boolean;
};

function testBannerClass(status: OpenBankingTestResult["status"]): string {
  if (status === "connected_successfully") {
    return "border-emerald-300/40 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200";
  }
  return "border-red-300/40 bg-red-500/10 text-red-800 dark:text-red-200";
}

/** Admin-only: minimal Open Banking provider credentials (secrets stay on server). */
export function OpenBankingSettingsForm({ readOnly = false }: OpenBankingSettingsFormProps) {
  const defaultRedirect = useMemo(() => {
    if (typeof window === "undefined") return "";
    return `${window.location.origin}/open-banking/callback`;
  }, []);

  const [status, setStatus] = useState<OpenBankingConfigStatus | null>(null);
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [redirectUrl, setRedirectUrl] = useState("");
  const [environment, setEnvironment] = useState<"sandbox" | "live">("sandbox");
  const [secretSet, setSecretSet] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<OpenBankingTestResult | null>(null);
  const [busy, setBusy] = useState<"save" | "test" | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<unknown>("/finance/integrations/open-banking/status");
      const parsed = openBankingConfigStatusSchema.parse(data);
      setStatus(parsed);
      setClientId(parsed.application_id || parsed.secret_id);
      setEnvironment(parsed.environment === "PRODUCTION" ? "live" : "sandbox");
      setRedirectUrl(parsed.redirect_url || defaultRedirect);
      setSecretSet(parsed.private_key_set || parsed.secret_key_set);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load settings");
    } finally {
      setLoading(false);
    }
  }, [defaultRedirect]);

  useEffect(() => {
    if (defaultRedirect && !redirectUrl) setRedirectUrl(defaultRedirect);
  }, [defaultRedirect, redirectUrl]);

  useEffect(() => {
    void load();
  }, [load]);

  function buildPayload() {
    return {
      provider: "enable_banking" as const,
      client_id: clientId.trim(),
      client_secret: clientSecret.trim(),
      redirect_url: redirectUrl.trim(),
      environment,
      country: "gb",
      scopes: "accounts,transactions",
      webhook_url: "",
    };
  }

  async function save() {
    setError(null);
    setMessage(null);
    setTestResult(null);
    if (!clientId.trim()) {
      setError("Client ID is missing — paste your Application ID from Enable Control Panel.");
      return;
    }
    if (!secretSet && !clientSecret.trim()) {
      setError("Client Secret is missing — paste your private.pem file contents.");
      return;
    }
    setBusy("save");
    try {
      await apiClient.put("/finance/integrations/open-banking/settings/setup", buildPayload());
      setClientSecret("");
      setSecretSet(true);
      setMessage("Saved securely. You can test the connection, then connect banks.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(null);
    }
  }

  async function testConnection() {
    setError(null);
    setTestResult(null);
    setBusy("test");
    try {
      if (!status?.configured) {
        await apiClient.put("/finance/integrations/open-banking/settings/setup", buildPayload());
        await load();
      }
      const data = await apiClient.post<unknown>("/finance/integrations/open-banking/test");
      setTestResult(openBankingTestResultSchema.parse(data));
    } catch (err) {
      setTestResult({
        status: "provider_rejected_credentials",
        message: err instanceof Error ? err.message : "Connection test failed",
        details: {},
      });
    } finally {
      setBusy(null);
    }
  }

  const redirectExample = redirectUrl || defaultRedirect;

  return (
    <div className="space-y-6">
      <p className="text-sm text-[var(--muted)]">
        One-time admin setup for Enable Banking (UK Open Banking). After this, use{" "}
        <Link href="/finance/connect" className="underline">
          Bank Connections
        </Link>{" "}
        to link each account.
      </p>

      <OpenBankingSetupInstructions redirectUrlExample={redirectExample} />

      {message ? (
        <p className="rounded-lg border border-emerald-300/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-900 dark:text-emerald-200">
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="rounded-lg border border-red-300/40 bg-red-500/10 px-3 py-2 text-sm text-red-800 dark:text-red-200">
          {error}
        </p>
      ) : null}
      {testResult ? (
        <p className={`rounded-lg border px-3 py-2 text-sm ${testBannerClass(testResult.status)}`}>
          {testResult.message}
        </p>
      ) : null}

      <div className="solar-card space-y-4">
        <h2 className="text-lg font-semibold">Open Banking Settings</h2>

        <label className="block text-sm">
          <span className="mb-1 block font-medium">Provider</span>
          <span className="mb-2 block text-xs text-[var(--muted)]">
            Enable Banking — supports Lloyds, MBNA, Virgin Money and other UK banks via official Open
            Banking.
          </span>
          <input className="solar-input w-full max-w-md" value="Enable Banking" disabled readOnly />
        </label>

        <label className="block text-sm">
          <span className="mb-1 block font-medium">Client ID</span>
          <span className="mb-2 block text-xs text-[var(--muted)]">
            Paste Application ID from Enable Control Panel → your app.
          </span>
          <input
            className="solar-input w-full font-mono text-xs"
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            disabled={readOnly || loading}
            autoComplete="off"
          />
        </label>

        <label className="block text-sm">
          <span className="mb-1 block font-medium">Client Secret</span>
          <span className="mb-2 block text-xs text-[var(--muted)]">
            Paste full contents of private.pem (certificate key, not a password).
            {secretSet ? " Leave blank to keep existing." : ""}
          </span>
          <textarea
            className="solar-input min-h-[100px] w-full font-mono text-xs"
            value={clientSecret}
            onChange={(e) => setClientSecret(e.target.value)}
            disabled={readOnly || loading}
            placeholder="-----BEGIN RSA PRIVATE KEY-----"
            autoComplete="off"
          />
        </label>

        <label className="block text-sm">
          <span className="mb-1 block font-medium">Redirect URL</span>
          <span className="mb-2 block text-xs text-[var(--muted)]">
            Must match exactly in Enable Control Panel and here.
          </span>
          <input
            className="solar-input w-full font-mono text-xs"
            value={redirectUrl}
            onChange={(e) => setRedirectUrl(e.target.value)}
            disabled={readOnly || loading}
            autoComplete="off"
          />
        </label>

        <label className="block text-sm max-w-xs">
          <span className="mb-1 block font-medium">Sandbox / Live</span>
          <select
            className="solar-input w-full"
            value={environment}
            onChange={(e) => setEnvironment(e.target.value as "sandbox" | "live")}
            disabled={readOnly || loading}
          >
            <option value="sandbox">Sandbox</option>
            <option value="live">Live</option>
          </select>
        </label>

        {!readOnly ? (
          <div className="flex flex-wrap gap-2 border-t border-[var(--border)] pt-4">
            <button
              type="button"
              className="solar-btn-secondary"
              disabled={busy !== null || loading}
              onClick={() => void save()}
            >
              {busy === "save" ? "Saving…" : "Save"}
            </button>
            <button
              type="button"
              className="solar-btn-secondary"
              disabled={busy !== null || loading}
              onClick={() => void testConnection()}
            >
              {busy === "test" ? "Testing…" : "Test connection"}
            </button>
            <Link href="/finance/connect" className="solar-btn-primary">
              Connect banks →
            </Link>
          </div>
        ) : null}
      </div>
    </div>
  );
}
