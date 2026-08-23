"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner, SuccessBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { apiClient } from "@/lib/api-client";
import { notifyFinanceChanged } from "@/lib/finance-events";
import { formatGbp } from "@/lib/money";
import { formatDataQualityIssue } from "@/lib/finance-labels";
import { canWrite } from "@/lib/permissions";
import { useRequireAuth } from "@/lib/use-require-auth";

type QualityTxn = {
  id: number;
  description: string;
  amount_gbp?: number;
  posted_on?: string;
  scope?: string;
  issue?: string;
  href?: string;
};

type QualityReport = {
  transaction_count: number;
  uncategorised_count: number;
  transfer_review_count: number;
  missing_dates_count: number;
  transfer_count?: number;
  uncategorised?: QualityTxn[];
  missing_dates?: QualityTxn[];
  transfer_review?: QualityTxn[];
  duplicate_candidate_groups: Array<Array<{ id: number; description: string; amount_gbp: number }>>;
  large_transactions: Array<{ id: number; description: string; amount_gbp: number; posted_on: string }>;
  possible_wrong_scope: Array<{
    id: number;
    description: string;
    scope: string;
    issue: string;
    posted_on?: string;
    href?: string;
  }>;
  message: string;
  full_ledger?: boolean;
};

export default function DataQualityPage() {
  const { user, gated, redirecting } = useRequireAuth();
  const writable = canWrite(user);
  const [report, setReport] = useState<QualityReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setReport(await apiClient.get<QualityReport>("/finance/data-quality"));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data quality");
    }
  }, []);

  useEffect(() => {
    if (gated || !user) return;
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [gated, user, load]);

  async function runAction(path: string, label: string) {
    if (!writable || busy) return;
    setBusy(label);
    setStatus(null);
    setError(null);
    try {
      const result = await apiClient.post<{ message?: string }>(path, {});
      setStatus(result.message || `${label} finished.`);
      notifyFinanceChanged();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : `${label} failed`);
    } finally {
      setBusy(null);
    }
  }

  if (gated) {
    return <AuthLoadingShell redirecting={redirecting} />;
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Data quality"
        description="Full-ledger counts with repair actions. Financial records are never auto-deleted from the report alone."
      />
      <div className="mt-6 space-y-6">
        {error ? <ErrorBanner message={error} /> : null}
        {status ? <SuccessBanner message={status} /> : null}
        {!report ? (
          <p className="text-sm text-[var(--muted)]">Loading…</p>
        ) : (
          <>
            <p className="text-sm text-[var(--muted)]">{report.message}</p>
            {writable ? (
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="solar-btn-primary"
                  disabled={Boolean(busy)}
                  onClick={() => void runAction("/finance/data-quality/backfill-dates", "Backfill dates")}
                >
                  {busy === "Backfill dates" ? "Working…" : "Backfill missing dates"}
                </button>
                <button
                  type="button"
                  className="solar-btn-ghost"
                  disabled={Boolean(busy)}
                  onClick={() => void runAction("/finance/data-quality/apply-rules", "Apply rules")}
                >
                  {busy === "Apply rules" ? "Working…" : "Apply rules to uncategorised"}
                </button>
                <button
                  type="button"
                  className="solar-btn-ghost"
                  disabled={Boolean(busy)}
                  onClick={() => void runAction("/finance/data-quality/resolve-review", "Resolve review")}
                >
                  {busy === "Resolve review" ? "Working…" : "Resolve false transfers / review"}
                </button>
              </div>
            ) : null}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-xl border border-[var(--border)] p-4">
                <p className="text-xs text-[var(--muted)]">Transactions</p>
                <p className="text-2xl font-semibold">{report.transaction_count}</p>
              </div>
              <div className="rounded-xl border border-[var(--border)] p-4">
                <p className="text-xs text-[var(--muted)]">Uncategorised</p>
                <p className="text-2xl font-semibold">{report.uncategorised_count}</p>
              </div>
              <div className="rounded-xl border border-[var(--border)] p-4">
                <p className="text-xs text-[var(--muted)]">Transfer review</p>
                <p className="text-2xl font-semibold">{report.transfer_review_count}</p>
              </div>
              <div className="rounded-xl border border-[var(--border)] p-4">
                <p className="text-xs text-[var(--muted)]">Missing dates</p>
                <p className="text-2xl font-semibold">{report.missing_dates_count}</p>
              </div>
            </div>
            <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
              <h2 className="font-semibold">Missing dates</h2>
              <ul className="mt-3 space-y-2 text-sm">
                {(report.missing_dates || []).length === 0 ? (
                  <li className="text-[var(--muted)]">None</li>
                ) : (
                  (report.missing_dates || []).map((item) => (
                    <li key={item.id}>
                      <Link href={item.href || `/finance/transactions?q=${item.id}`} className="underline">
                        #{item.id}
                      </Link>{" "}
                      · {item.description || "(no description)"}
                    </li>
                  ))
                )}
              </ul>
            </section>
            <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
              <h2 className="font-semibold">Uncategorised sample</h2>
              <ul className="mt-3 space-y-2 text-sm">
                {(report.uncategorised || []).length === 0 ? (
                  <li className="text-[var(--muted)]">None</li>
                ) : (
                  (report.uncategorised || []).map((item) => (
                    <li key={item.id}>
                      <Link href={item.href || `/finance/transactions?q=${item.id}`} className="underline">
                        #{item.id}
                      </Link>{" "}
                      · {item.posted_on || "undated"} · {item.description}
                    </li>
                  ))
                )}
              </ul>
              <Link href="/finance/transactions?filter=uncategorised" className="mt-3 inline-block text-sm underline">
                Review all uncategorised
              </Link>
            </section>
            <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
              <h2 className="font-semibold">Possible wrong scope</h2>
              <ul className="mt-3 space-y-2 text-sm">
                {report.possible_wrong_scope.length === 0 ? (
                  <li className="text-[var(--muted)]">None flagged</li>
                ) : (
                  report.possible_wrong_scope.map((item) => (
                    <li key={item.id}>
                      <Link href={item.href || `/finance/transactions?q=${item.id}`} className="underline">
                        #{item.id}
                      </Link>{" "}
                      · {item.description} · {item.scope} · {formatDataQualityIssue(item.issue)}
                    </li>
                  ))
                )}
              </ul>
            </section>
            <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
              <h2 className="font-semibold">Large transactions</h2>
              <ul className="mt-3 space-y-2 text-sm">
                {report.large_transactions.length === 0 ? (
                  <li className="text-[var(--muted)]">None</li>
                ) : (
                  report.large_transactions.map((item) => (
                    <li key={item.id}>
                      <Link href={`/finance/transactions?q=${item.id}`} className="underline">
                        #{item.id}
                      </Link>{" "}
                      · {item.posted_on} · {item.description} · {formatGbp(item.amount_gbp)}
                    </li>
                  ))
                )}
              </ul>
            </section>
            <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
              <h2 className="font-semibold">Duplicate candidates</h2>
              <p className="mt-1 text-sm text-[var(--muted)]">
                Same day, amount and description with different fingerprints — review manually.
              </p>
              <p className="mt-2 text-sm">{report.duplicate_candidate_groups.length} group(s)</p>
            </section>
          </>
        )}
      </div>
    </AppShell>
  );
}
