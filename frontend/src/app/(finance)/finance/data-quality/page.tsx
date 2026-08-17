"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { apiClient } from "@/lib/api-client";
import { useRequireAuth } from "@/lib/use-require-auth";
import { formatGbp } from "@/lib/money";

type QualityReport = {
  transaction_count: number;
  uncategorised_count: number;
  transfer_review_count: number;
  missing_dates_count: number;
  duplicate_candidate_groups: Array<Array<{ id: number; description: string; amount_gbp: number }>>;
  large_transactions: Array<{ id: number; description: string; amount_gbp: number; posted_on: string }>;
  possible_wrong_scope: Array<{
    id: number;
    description: string;
    scope: string;
    issue: string;
    posted_on?: string;
  }>;
  message: string;
};

export default function DataQualityPage() {
  const { user, gated, redirecting } = useRequireAuth();
  const [report, setReport] = useState<QualityReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setReport(await apiClient.get<QualityReport>("/finance/data-quality"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data quality");
    }
  }, []);

  useEffect(() => {
    if (gated || !user) return;
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [gated, user, load]);

  if (gated) {
    return <AuthLoadingShell redirecting={redirecting} />;
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Data quality"
        description="Issues are reported only — financial records are never auto-deleted."
      />
      <div className="mt-6 space-y-6">
        {error ? <ErrorBanner message={error} /> : null}
        {!report ? (
          <p className="text-sm text-[var(--muted)]">Loading…</p>
        ) : (
          <>
            <p className="text-sm text-[var(--muted)]">{report.message}</p>
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
              <h2 className="font-semibold">Possible wrong scope</h2>
              <ul className="mt-3 space-y-2 text-sm">
                {report.possible_wrong_scope.length === 0 ? (
                  <li className="text-[var(--muted)]">None flagged</li>
                ) : (
                  report.possible_wrong_scope.map((item) => (
                    <li key={item.id}>
                      {item.posted_on ? null : null}
                      {item.description} · {item.scope} · {item.issue}
                    </li>
                  ))
                )}
              </ul>
              <Link href="/finance/transactions?filter=uncategorised" className="mt-3 inline-block text-sm underline">
                Review uncategorised
              </Link>
            </section>
            <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
              <h2 className="font-semibold">Large transactions</h2>
              <ul className="mt-3 space-y-2 text-sm">
                {report.large_transactions.length === 0 ? (
                  <li className="text-[var(--muted)]">None</li>
                ) : (
                  report.large_transactions.map((item) => (
                    <li key={item.id}>
                      {item.posted_on} · {item.description} · {formatGbp(item.amount_gbp)}
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
