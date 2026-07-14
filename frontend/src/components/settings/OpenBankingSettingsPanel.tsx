"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { openBankingConfigStatusSchema, type OpenBankingConfigStatus } from "@/lib/finance-schemas";

type OpenBankingSettingsPanelProps = {
  readOnly?: boolean;
};

export function OpenBankingSettingsPanel({ readOnly = false }: OpenBankingSettingsPanelProps) {
  const { user } = useAuth();
  const [status, setStatus] = useState<OpenBankingConfigStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<unknown>("/finance/integrations/open-banking/status");
      setStatus(openBankingConfigStatusSchema.parse(data));
    } catch (err) {
      setStatus(null);
      setError(err instanceof Error ? err.message : "Failed to load Open Banking status");
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void load();
  }, [load]);

  const configured = status?.configured ?? false;

  return (
    <section className="solar-card space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">Open Banking (personal)</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Connect Lloyds, Virgin, MBNA and other personal accounts. Credentials and linking live on
            the Connect banks page.
          </p>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-xs font-medium ${
            configured
              ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
              : "bg-amber-500/15 text-amber-800 dark:text-amber-200"
          }`}
        >
          {loading ? "Loading…" : configured ? "Configured" : "Not configured"}
        </span>
      </div>

      {error ? (
        <p className="rounded-lg border border-red-300/40 bg-red-500/10 px-3 py-2 text-sm text-red-800 dark:text-red-200">
          {error}
        </p>
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

      {status?.last_sync_at ? (
        <p className="text-xs text-[var(--muted)]">
          Last sync: {new Date(status.last_sync_at).toLocaleString("en-GB")}
        </p>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Link href="/finance/connect" className="solar-btn-primary">
          Connect banks →
        </Link>
      </div>

      {readOnly ? (
        <p className="text-xs text-[var(--muted)]">Admin access is required to change Open Banking settings.</p>
      ) : null}
    </section>
  );
}
