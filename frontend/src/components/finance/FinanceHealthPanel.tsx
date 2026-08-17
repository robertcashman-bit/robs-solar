"use client";

import { useCallback, useState } from "react";

import { ErrorBanner, SuccessBanner } from "@/components/shared/Banners";
import { apiClient } from "@/lib/api-client";
import { notifyFinanceChanged } from "@/lib/finance-events";
import { useFinanceReload } from "@/lib/use-finance-reload";

type HealthPayload = {
  ok?: boolean;
  db_read?: boolean;
  db_write?: boolean;
  database_backend?: string;
  ephemeral_database?: boolean;
  web_backup_configured?: boolean;
  last_import?: { source?: string; imported?: number; created_at?: string } | null;
  last_backup?: { location?: string; created_at?: string } | null;
  last_health_check?: string | null;
  needs_review?: boolean;
  consistency?: { flags?: Array<{ check: string; note?: string; ok?: boolean }> };
};

export function FinanceHealthPanel({ canEdit }: { canEdit: boolean }) {
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await apiClient.get<HealthPayload>("/finance/health");
      setHealth(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load finance health");
    }
  }, []);

  useFinanceReload(load, true);

  async function selfHeal() {
    if (!canEdit || busy) return;
    setBusy(true);
    try {
      const result = await apiClient.post<{ repaired?: string[]; source_transactions_unchanged?: boolean }>(
        "/finance/health/self-heal",
      );
      setStatus(
        result.source_transactions_unchanged
          ? `Self-heal finished. Source transactions unchanged. ${result.repaired?.join(", ") || "No cache rebuild needed."}`
          : "Self-heal finished. Review the ledger.",
      );
      notifyFinanceChanged();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Self-heal failed");
    } finally {
      setBusy(false);
    }
  }

  async function backupNow() {
    if (!canEdit || busy) return;
    setBusy(true);
    try {
      const result = await apiClient.post<{ location?: string }>("/finance/backups");
      setStatus(`Backup saved (${result.location || "local"}).`);
      notifyFinanceChanged();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Backup failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="solar-card space-y-3">
      <h2 className="text-lg font-semibold">Finance health</h2>
      <p className="text-sm text-[var(--muted)]">
        Checks the database and flags inconsistencies. Self-heal only rebuilds derived
        caches. It never invents or edits imported transactions.
      </p>
      {error ? <ErrorBanner message={error} /> : null}
      {status ? <SuccessBanner message={status} /> : null}
      {health ? (
        <ul className="space-y-1 text-sm">
          <li>Database: {health.database_backend} {health.db_write ? "read/write ok" : "write failed"}</li>
          <li>
            Persistence:{" "}
            {health.ephemeral_database
              ? "Hosted SQLite under /tmp is wiped on deploy — set a durable DATABASE_URL or enable web backup."
              : "Durable store in use."}
          </li>
          <li>Web backup: {health.web_backup_configured ? "configured" : "not configured"}</li>
          <li>
            Last import:{" "}
            {health.last_import
              ? `${health.last_import.source} (${health.last_import.imported} rows)`
              : "none"}
          </li>
          <li>
            Last backup:{" "}
            {health.last_backup
              ? `${health.last_backup.location} · ${new Date(health.last_backup.created_at || "").toLocaleString("en-GB")}`
              : "none yet — tap Backup now"}
          </li>
          <li>Needs review: {health.needs_review ? "yes" : "no"}</li>
        </ul>
      ) : (
        <p className="text-sm text-[var(--muted)]">Loading health…</p>
      )}
      {canEdit ? (
        <div className="flex flex-wrap gap-2">
          <button type="button" className="solar-btn-primary" onClick={() => void selfHeal()} disabled={busy}>
            {busy ? "Working…" : "Self-heal caches"}
          </button>
          <button type="button" className="solar-btn-ghost" onClick={() => void backupNow()} disabled={busy}>
            Backup now
          </button>
        </div>
      ) : null}
    </section>
  );
}
