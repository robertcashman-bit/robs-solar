"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner, SuccessBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { notifyFinanceChanged } from "@/lib/finance-events";
import { formatGbp } from "@/lib/money";
import { canWrite } from "@/lib/permissions";

type ParsedStatement = {
  format: string;
  headers: string[];
  column_mapping: Record<string, string>;
  rows: Array<Record<string, unknown>>;
  rejects: Array<{ index: number; reason: string }>;
  detected: number;
};

type PreviewResult = {
  detected: number;
  new_count: number;
  duplicate_count: number;
  rejected_count: number;
  money_in_gbp: number;
  money_out_gbp: number;
  date_from: string;
  date_to: string;
  warnings: string[];
};

export default function ImportPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const writable = canWrite(user);
  const [file, setFile] = useState<File | null>(null);
  const [accountName, setAccountName] = useState("Personal current");
  const [scope, setScope] = useState<"personal" | "business">("personal");
  const [parsed, setParsed] = useState<ParsedStatement | null>(null);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<"parse" | "preview" | "commit" | null>(null);

  const parseFile = useCallback(async () => {
    if (!file) return;
    setBusy("parse");
    setError(null);
    setMessage(null);
    setPreview(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("account_name", accountName);
      form.append("scope", scope);
      const data = await apiClient.postForm<ParsedStatement>(
        "/finance/transactions/import/parse",
        form,
      );
      setParsed(data);
      setMessage(
        `Detected ${data.rows.length} row(s) as ${data.format.toUpperCase()}` +
          (data.rejects.length ? ` · ${data.rejects.length} parse reject(s)` : ""),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Parse failed");
    } finally {
      setBusy(null);
    }
  }, [accountName, file, scope]);

  const runPreview = useCallback(async () => {
    if (!parsed?.rows.length) return;
    setBusy("preview");
    setError(null);
    try {
      const data = await apiClient.post<PreviewResult>("/finance/transactions/import/preview", {
        source: parsed.format === "csv" ? "csv" : parsed.format,
        rows: parsed.rows,
      });
      setPreview(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setBusy(null);
    }
  }, [parsed]);

  const commit = useCallback(async () => {
    if (!parsed?.rows.length) return;
    setBusy("commit");
    setError(null);
    try {
      const data = await apiClient.post<{
        imported: number;
        duplicate_count: number;
        rejected_count: number;
      }>("/finance/transactions/import/commit", {
        source: parsed.format === "csv" ? "csv" : parsed.format,
        rows: parsed.rows,
      });
      notifyFinanceChanged();
      setMessage(
        `Imported ${data.imported}. Already existed: ${data.duplicate_count}. Rejected: ${data.rejected_count}.`,
      );
      setPreview(null);
      setParsed(null);
      setFile(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Commit failed");
    } finally {
      setBusy(null);
    }
  }, [parsed]);

  if (authLoading || !user) {
    if (!authLoading && !user) router.replace("/login");
    return <AuthLoadingShell />;
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Import statements"
        description="Upload CSV, OFX, QFX or QIF. Preview before commit. Duplicates are blocked by fingerprint."
      />
      {!writable ? (
        <p className="mt-4 text-sm text-[var(--muted)]">Viewer accounts cannot import.</p>
      ) : (
        <div className="mt-6 space-y-6">
          {error ? <ErrorBanner message={error} /> : null}
          {message ? <SuccessBanner message={message} /> : null}
          <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block text-sm">
                <span className="text-[var(--muted)]">Account name</span>
                <input
                  className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-2"
                  value={accountName}
                  onChange={(e) => setAccountName(e.target.value)}
                />
              </label>
              <label className="block text-sm">
                <span className="text-[var(--muted)]">Scope</span>
                <select
                  className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-2"
                  value={scope}
                  onChange={(e) => setScope(e.target.value as "personal" | "business")}
                >
                  <option value="personal">Personal</option>
                  <option value="business">Business (Defence Legal Services Ltd)</option>
                </select>
              </label>
            </div>
            <label className="mt-4 block text-sm">
              <span className="text-[var(--muted)]">Statement file</span>
              <input
                type="file"
                accept=".csv,.ofx,.qfx,.qif,text/csv"
                className="mt-1 block w-full text-sm"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                disabled={!file || busy !== null}
                onClick={() => void parseFile()}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {busy === "parse" ? "Parsing…" : "Parse file"}
              </button>
              <button
                type="button"
                disabled={!parsed?.rows.length || busy !== null}
                onClick={() => void runPreview()}
                className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-medium disabled:opacity-50"
              >
                {busy === "preview" ? "Checking…" : "Preview duplicates"}
              </button>
              <button
                type="button"
                disabled={!parsed?.rows.length || busy !== null}
                onClick={() => void commit()}
                className="rounded-lg bg-teal-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {busy === "commit" ? "Importing…" : "Commit import"}
              </button>
            </div>
          </section>

          {preview ? (
            <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 text-sm">
              <h2 className="font-semibold">Import preview</h2>
              <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                <li>New: {preview.new_count}</li>
                <li>Already existed: {preview.duplicate_count}</li>
                <li>Rejected: {preview.rejected_count}</li>
                <li>
                  Money in / out: {formatGbp(preview.money_in_gbp)} / {formatGbp(preview.money_out_gbp)}
                </li>
                <li>
                  Dates: {preview.date_from || "—"} → {preview.date_to || "—"}
                </li>
              </ul>
              {preview.warnings?.length ? (
                <p className="mt-2 text-[var(--muted)]">{preview.warnings.join(" ")}</p>
              ) : null}
            </section>
          ) : null}

          {parsed?.rows.length ? (
            <section className="overflow-x-auto rounded-2xl border border-[var(--border)] bg-[var(--surface)]">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-[var(--border)] text-[var(--muted)]">
                  <tr>
                    <th className="px-3 py-2">Date</th>
                    <th className="px-3 py-2">Description</th>
                    <th className="px-3 py-2">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {parsed.rows.slice(0, 40).map((row, index) => (
                    <tr key={index} className="border-b border-[var(--border)]/60">
                      <td className="px-3 py-2 whitespace-nowrap">{String(row.posted_on)}</td>
                      <td className="px-3 py-2">{String(row.description)}</td>
                      <td className="px-3 py-2">{formatGbp(Number(row.amount_gbp) || 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {parsed.rows.length > 40 ? (
                <p className="px-3 py-2 text-xs text-[var(--muted)]">
                  Showing first 40 of {parsed.rows.length}
                </p>
              ) : null}
            </section>
          ) : null}
        </div>
      )}
    </AppShell>
  );
}
