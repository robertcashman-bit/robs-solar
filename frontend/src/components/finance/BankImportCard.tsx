"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import {
  trueLayerConfigStatusSchema,
  trueLayerSyncResultSchema,
  type TrueLayerConfigStatus,
} from "@/lib/finance-schemas";
import { notifyFinanceChanged } from "@/lib/finance-events";
import { canWrite } from "@/lib/permissions";

export const BANK_IMPORT_SESSION_KEY = "finance.bankImported";

type BankImportCardProps = {
  readOnly?: boolean;
  autoImport?: boolean;
  showSettingsLink?: boolean;
  deferMs?: number;
  onImported?: (message: string) => void;
};

export function BankImportCard({
  readOnly = false,
  autoImport = false,
  showSettingsLink = true,
  deferMs = 0,
  onImported,
}: BankImportCardProps) {
  const { user, loading: authLoading } = useAuth();
  const writable = canWrite(user) && !readOnly;
  const [banking, setBanking] = useState<TrueLayerConfigStatus | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"login" | "import" | null>(null);
  const autoStarted = useRef(false);

  const load = useCallback(async () => {
    if (!user) return;
    try {
      const data = await apiClient.get<unknown>("/finance/integrations/open-banking/status");
      setBanking(trueLayerConfigStatusSchema.parse(data));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load bank connection");
    }
  }, [user]);

  useEffect(() => {
    if (authLoading || !user) return;
    const timer = window.setTimeout(() => void load(), deferMs);
    return () => window.clearTimeout(timer);
  }, [authLoading, user, load, deferMs]);

  const importNow = useCallback(async () => {
    setBusy("import");
    setError(null);
    setMessage(null);
    try {
      const data = await apiClient.post<unknown>("/finance/integrations/open-banking/sync");
      const parsed = trueLayerSyncResultSchema.parse(data);
      window.sessionStorage.setItem(BANK_IMPORT_SESSION_KEY, "1");
      setMessage(parsed.message);
      notifyFinanceChanged();
      onImported?.(parsed.message);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setBusy(null);
    }
  }, [load, onImported]);

  useEffect(() => {
    if (!autoImport || !writable || !banking?.connected || autoStarted.current) {
      return;
    }
    if (window.sessionStorage.getItem(BANK_IMPORT_SESSION_KEY)) {
      return;
    }
    autoStarted.current = true;
    const timer = window.setTimeout(() => {
      void importNow();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [autoImport, writable, banking?.connected, importNow]);

  async function loginAndImport() {
    setBusy("login");
    setError(null);
    try {
      if (banking?.connected) {
        await importNow();
        return;
      }
      const data = await apiClient.get<{ authorize_url: string }>(
        "/finance/integrations/open-banking/authorize",
      );
      window.location.href = data.authorize_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start bank login");
      setBusy(null);
    }
  }

  if (authLoading) {
    return <p className="text-sm text-[var(--muted)]">Checking bank connection…</p>;
  }

  if (!banking?.configured) {
    return null;
  }

  return (
    <section className="solar-card space-y-3">
      <div>
        <h2 className="text-lg font-semibold">Log in and pull everything in</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Log in to your UK bank in this app. We pull accounts, cards, and Funding
          Circle payments from that feed. No bank password is stored here. Funding
          Circle has no borrower login API, and the loan is not in QuickFile.
        </p>
      </div>
      {error ? <p className="text-sm text-red-500">{error}</p> : null}
      {message ? <p className="text-sm text-emerald-500">{message}</p> : null}
      {banking?.last_sync_at ? (
        <p className="text-sm text-[var(--muted)]">
          Last pull {banking.last_sync_at.slice(0, 10)}
          {banking.connected ? " · Bank connected" : ""}
        </p>
      ) : null}
      {writable ? (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="solar-btn-primary"
            onClick={() => void loginAndImport()}
            disabled={busy != null || !banking?.configured}
          >
            {busy === "login" || busy === "import"
              ? "Importing…"
              : banking?.connected
                ? "Pull latest from your bank"
                : "Log in to your bank and import"}
          </button>
          {showSettingsLink && !banking?.configured ? (
            <Link href="/settings" className="solar-btn-ghost">
              Save bank credentials first
            </Link>
          ) : null}
        </div>
      ) : null}
      {!banking?.configured ? (
        <p className="text-sm text-[var(--muted)]">
          Save TrueLayer Open Banking credentials in Settings once. After that, bank
          login is enough.
        </p>
      ) : null}
    </section>
  );
}
