"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { z } from "zod";

import { OpenBankingSetupInstructions } from "@/components/finance/OpenBankingSetupInstructions";
import { apiClient } from "@/lib/api-client";
import {
  openBankingConfigStatusSchema,
  openBankingConnectResponseSchema,
  openBankingInstitutionSchema,
  openBankingSyncResultSchema,
  openBankingTestResultSchema,
  type OpenBankingConfigStatus,
  type OpenBankingInstitution,
  type OpenBankingTestResult,
} from "@/lib/finance-schemas";

type OpenBankingSetupPageProps = {
  readOnly?: boolean;
};

const POPULAR_BANKS = [
  { query: "Mock ASPSP", label: "Mock ASPSP (sandbox test)" },
  { query: "Lloyds", label: "Lloyds Bank" },
  { query: "MBNA", label: "MBNA" },
  { query: "Virgin", label: "Virgin Money" },
] as const;

function testBannerClass(status: OpenBankingTestResult["status"]): string {
  if (status === "connected_successfully") {
    return "border-emerald-300/40 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200";
  }
  if (status === "further_bank_authorisation_required") {
    return "border-amber-300/40 bg-amber-500/10 text-amber-900 dark:text-amber-200";
  }
  return "border-red-300/40 bg-red-500/10 text-red-800 dark:text-red-200";
}

/** Plain-English Open Banking setup: credentials, test, and bank connect. */
export function OpenBankingSetupPage({ readOnly = false }: OpenBankingSetupPageProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const defaultRedirect = useMemo(() => {
    if (typeof window === "undefined") return "";
    return `${window.location.origin}/open-banking/callback`;
  }, []);

  const [status, setStatus] = useState<OpenBankingConfigStatus | null>(null);
  const [provider, setProvider] = useState<"enable_banking" | "gocardless">("enable_banking");
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [redirectUrl, setRedirectUrl] = useState("");
  const [environment, setEnvironment] = useState<"sandbox" | "live">("sandbox");
  const [country, setCountry] = useState("gb");
  const [scopes, setScopes] = useState("accounts,transactions");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [secretSet, setSecretSet] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<string[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<OpenBankingTestResult | null>(null);
  const [busy, setBusy] = useState<"save" | "test" | "connect" | "search" | "finalize" | null>(null);
  const [loading, setLoading] = useState(true);
  const [bankQuery, setBankQuery] = useState("");
  const [institutions, setInstitutions] = useState<OpenBankingInstitution[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<unknown>("/finance/integrations/open-banking/status");
      const parsed = openBankingConfigStatusSchema.parse(data);
      setStatus(parsed);
      setProvider(parsed.provider);
      setClientId(parsed.application_id || parsed.secret_id);
      setEnvironment(parsed.environment === "PRODUCTION" ? "live" : "sandbox");
      setRedirectUrl(parsed.redirect_url || defaultRedirect);
      setCountry(parsed.country || "gb");
      setScopes(parsed.scopes || "accounts,transactions");
      setWebhookUrl(parsed.webhook_url || "");
      setSecretSet(parsed.private_key_set || parsed.secret_key_set);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load Open Banking status");
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

  const finalizeConnection = useCallback(
    async (lookup: string, code: string | null) => {
      setBusy("finalize");
      setMessage(null);
      setError(null);
      try {
        const payload: Record<string, string> = searchParams.get("state")
          ? { state: lookup }
          : { reference: lookup };
        if (code) payload.code = code;
        const data = await apiClient.post<unknown>(
          "/finance/integrations/open-banking/finalize",
          payload,
        );
        const result = openBankingSyncResultSchema.parse(data);
        setMessage(result.message || "Bank account connected successfully.");
        await load();
        router.replace("/finance/open-banking/setup");
      } catch {
        setError("Bank requires reconnection. Press Connect and sign in again at your bank.");
      } finally {
        setBusy(null);
      }
    },
    [load, router, searchParams],
  );

  useEffect(() => {
    if (readOnly) return;
    const callback = searchParams.get("open_banking");
    const lookup = searchParams.get("state") || searchParams.get("ref");
    const code = searchParams.get("code");
    if (callback === "callback" && lookup) {
      void finalizeConnection(lookup, code);
    }
  }, [readOnly, searchParams, finalizeConnection]);

  function buildPayload() {
    return {
      provider,
      client_id: clientId.trim(),
      client_secret: clientSecret.trim(),
      redirect_url: redirectUrl.trim(),
      environment,
      country: country.trim().toLowerCase(),
      scopes: scopes.trim(),
      webhook_url: webhookUrl.trim(),
    };
  }

  async function save() {
    setError(null);
    setMessage(null);
    setTestResult(null);
    setFieldErrors([]);

    const errors: string[] = [];
    if (!clientId.trim()) {
      errors.push(
        provider === "enable_banking"
          ? "Client ID is missing — paste your Application ID from Enable Control Panel."
          : "Client ID is missing — paste your Secret ID from GoCardless.",
      );
    }
    if (!secretSet && !clientSecret.trim()) {
      errors.push(
        provider === "enable_banking"
          ? "Client Secret is missing — paste your private.pem file contents."
          : "Client Secret is missing — paste your Secret key from GoCardless.",
      );
    }
    if (!redirectUrl.trim()) {
      errors.push("Redirect URL is missing.");
    }

    if (errors.length) {
      setFieldErrors(errors);
      setError(errors[0]);
      return;
    }

    setBusy("save");
    try {
      await apiClient.put("/finance/integrations/open-banking/settings/setup", buildPayload());
      setClientSecret("");
      setSecretSet(true);
      setMessage("Saved securely. Test the connection, then connect a bank account.");
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
    setFieldErrors([]);
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

  async function searchInstitutions(query: string) {
    setBusy("search");
    setError(null);
    try {
      const data = await apiClient.get<unknown>(
        `/finance/integrations/open-banking/institutions?country=${encodeURIComponent(country)}&q=${encodeURIComponent(query)}`,
      );
      setInstitutions(z.array(openBankingInstitutionSchema).parse(data));
    } catch {
      setInstitutions([]);
      setError("Could not search banks. Save and test your connection first.");
    } finally {
      setBusy(null);
    }
  }

  async function connectInstitution(institution: OpenBankingInstitution) {
    if (!status?.configured) {
      setError("Save and test your Open Banking settings before connecting a bank.");
      return;
    }
    setBusy("connect");
    setError(null);
    setMessage(null);
    try {
      const connectData = await apiClient.post<unknown>("/finance/integrations/open-banking/connect", {
        institution_id: institution.id,
        institution_name: institution.name,
      });
      const result = openBankingConnectResponseSchema.parse(connectData);
      setMessage(`Taking you to ${result.institution_name} to sign in…`);
      window.location.href = result.link;
    } catch {
      setError("Could not start bank login. Check your settings and try again.");
    } finally {
      setBusy(null);
    }
  }

  const redirectExample = redirectUrl || defaultRedirect;
  const configured = status?.configured ?? false;

  return (
    <div className="space-y-6">
      <p className="text-sm text-[var(--muted)]">
        One-time setup for UK Open Banking (Lloyds, MBNA, Virgin Money, and more). After saving,
        test your connection and connect each bank. Day-to-day bank management lives on{" "}
        <Link href="/finance/connect" className="underline">
          Connect banks
        </Link>
        .
      </p>

      {readOnly ? (
        <p className="rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] px-3 py-2 text-sm text-[var(--muted)]">
          Admin access is required to change settings.{" "}
          {configured ? (
            <Link href="/finance/connect" className="underline">
              Connect banks
            </Link>
          ) : (
            "Ask an admin to complete setup."
          )}
        </p>
      ) : null}

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
      {fieldErrors.length > 1 ? (
        <ul className="rounded-lg border border-red-300/40 bg-red-500/10 px-3 py-2 text-sm text-red-800 dark:text-red-200">
          {fieldErrors.map((item) => (
            <li key={item} className="list-disc ml-4">
              {item}
            </li>
          ))}
        </ul>
      ) : null}
      {testResult ? (
        <p className={`rounded-lg border px-3 py-2 text-sm ${testBannerClass(testResult.status)}`}>
          {testResult.message}
        </p>
      ) : null}

      <div className="solar-card space-y-4">
        <h2 className="text-lg font-semibold">Step 1 — Provider credentials</h2>

        <label className="block text-sm">
          <span className="mb-1 block font-medium">Provider</span>
          <span className="mb-2 block text-xs text-[var(--muted)]">
            Enable Banking is recommended for UK banks. GoCardless / Nordigen is legacy only.
            TrueLayer, Plaid, Yapily, and Tink are not supported yet.
          </span>
          <select
            className="solar-input w-full max-w-md"
            value={provider}
            onChange={(e) => setProvider(e.target.value as "enable_banking" | "gocardless")}
            disabled={readOnly || loading}
          >
            <option value="enable_banking">Enable Banking (recommended for UK banks)</option>
            <option value="gocardless">GoCardless / Nordigen (legacy)</option>
          </select>
        </label>

        <label className="block text-sm">
          <span className="mb-1 block font-medium">Client ID</span>
          <span className="mb-2 block text-xs text-[var(--muted)]">
            {provider === "enable_banking"
              ? "Application ID from Enable Control Panel → your app."
              : "Secret ID from the GoCardless / Nordigen dashboard."}
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
            {provider === "enable_banking"
              ? "Full contents of private.pem (certificate key, not a password)."
              : "Secret key from GoCardless dashboard."}
            {secretSet ? " Leave blank to keep existing." : ""}
          </span>
          <textarea
            className="solar-input min-h-[100px] w-full font-mono text-xs"
            value={clientSecret}
            onChange={(e) => setClientSecret(e.target.value)}
            disabled={readOnly || loading}
            placeholder={
              provider === "enable_banking" ? "-----BEGIN RSA PRIVATE KEY-----" : "Secret key"
            }
            autoComplete="off"
          />
        </label>

        <label className="block text-sm">
          <span className="mb-1 block font-medium">Redirect URI</span>
          <span className="mb-2 block text-xs text-[var(--muted)]">
            Must match exactly in your provider dashboard and here.
          </span>
          <input
            className="solar-input w-full font-mono text-xs"
            value={redirectUrl}
            onChange={(e) => setRedirectUrl(e.target.value)}
            disabled={readOnly || loading}
            autoComplete="off"
          />
        </label>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Environment</span>
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

          <label className="block text-sm">
            <span className="mb-1 block font-medium">Bank country</span>
            <select
              className="solar-input w-full"
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              disabled={readOnly || loading}
            >
              <option value="gb">United Kingdom (GB)</option>
              <option value="ie">Ireland (IE)</option>
            </select>
          </label>
        </div>

        <label className="block text-sm">
          <span className="mb-1 block font-medium">Scopes</span>
          <span className="mb-2 block text-xs text-[var(--muted)]">
            Pre-filled for account information and transactions.
          </span>
          <input
            className="solar-input w-full"
            value={scopes}
            onChange={(e) => setScopes(e.target.value)}
            disabled={readOnly || loading}
          />
        </label>

        <label className="block text-sm">
          <span className="mb-1 block font-medium">Webhook URL (optional)</span>
          <span className="mb-2 block text-xs text-[var(--muted)]">
            Only required if your provider asks for one — Enable Banking does not need this.
          </span>
          <input
            className="solar-input w-full font-mono text-xs"
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
            disabled={readOnly || loading}
            placeholder="https://"
            autoComplete="off"
          />
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
          </div>
        ) : null}
      </div>

      <div className="solar-card space-y-4">
        <h2 className="text-lg font-semibold">Step 2 — Connect a bank account</h2>
        <p className="text-sm text-[var(--muted)]">
          Save and test first. You will be redirected to your bank to sign in securely.
        </p>

        {!readOnly ? (
          <>
            <div className="flex flex-wrap gap-2">
              {POPULAR_BANKS.map((bank) => (
                <button
                  key={bank.query}
                  type="button"
                  className="solar-btn-secondary text-sm"
                  disabled={busy !== null || !configured}
                  onClick={() => void searchInstitutions(bank.query)}
                >
                  {bank.label}
                </button>
              ))}
            </div>

            <div className="flex flex-wrap gap-2">
              <input
                className="solar-input min-w-[200px] flex-1"
                value={bankQuery}
                onChange={(e) => setBankQuery(e.target.value)}
                placeholder="Search bank name…"
                disabled={busy !== null || !configured}
              />
              <button
                type="button"
                className="solar-btn-secondary"
                disabled={busy !== null || !configured || !bankQuery.trim()}
                onClick={() => void searchInstitutions(bankQuery.trim())}
              >
                {busy === "search" ? "Searching…" : "Search"}
              </button>
            </div>

            {institutions.length ? (
              <ul className="divide-y divide-[var(--border)] rounded-xl border border-[var(--border)]">
                {institutions.slice(0, 8).map((institution) => (
                  <li
                    key={institution.id}
                    className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm"
                  >
                    <span>{institution.name}</span>
                    <button
                      type="button"
                      className="solar-btn-primary text-xs"
                      disabled={busy !== null}
                      onClick={() => void connectInstitution(institution)}
                    >
                      {busy === "connect" ? "Connecting…" : "Connect"}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </>
        ) : null}

        {status?.linked_banks.length ? (
          <div className="rounded-xl border border-[var(--border)] px-4 py-3 text-sm">
            <p className="font-medium">Connected banks</p>
            <ul className="mt-2 list-disc pl-5 text-[var(--muted)]">
              {status.linked_banks.map((bank) => (
                <li key={bank}>{bank}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </div>
  );
}
