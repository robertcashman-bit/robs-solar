"use client";

import { useState } from "react";

import { ErrorBanner, SuccessBanner } from "@/components/shared/Banners";
import { downloadAuthenticatedExport, downloadTextFile, toCsv } from "@/lib/finance-export";
import { apiClient } from "@/lib/api-client";

type FinanceExportPanelProps = {
  reportRows?: Array<Record<string, string | number | boolean | null | undefined>>;
};

export function FinanceExportPanel({ reportRows }: FinanceExportPanelProps) {
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function exportTransactions(scope?: "personal" | "business") {
    setBusy(scope || "all");
    setError(null);
    setStatus(null);
    try {
      const query = scope ? `?scope=${scope}` : "";
      await downloadAuthenticatedExport(
        `/finance/export/transactions.csv${query}`,
        scope ? `transactions-${scope}.csv` : "transactions.csv",
      );
      setStatus("Transactions CSV downloaded.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setBusy(null);
    }
  }

  async function exportBudgetPlan() {
    setBusy("budget");
    setError(null);
    try {
      const plans = await apiClient.get<
        Array<{
          name: string;
          style: string;
          is_active: boolean;
          totals?: { total_spending_gbp?: number; surplus_gbp?: number };
        }>
      >("/finance/budgets");
      const rows = plans.map((plan) => ({
        name: plan.name,
        style: plan.style,
        active: plan.is_active,
        spending_gbp: plan.totals?.total_spending_gbp ?? "",
        surplus_gbp: plan.totals?.surplus_gbp ?? "",
      }));
      if (!rows.length) {
        setStatus("No budget plans to export.");
        return;
      }
      downloadTextFile("budget-plans.csv", toCsv(rows), "text/csv");
      setStatus("Budget plans CSV downloaded.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Budget export failed");
    } finally {
      setBusy(null);
    }
  }

  function exportReportSnapshot() {
    if (!reportRows?.length) {
      setStatus("Open Reports first, or export transactions instead.");
      return;
    }
    downloadTextFile("finance-report.csv", toCsv(reportRows), "text/csv");
    setStatus("Report snapshot CSV downloaded.");
  }

  return (
    <section className="space-y-3 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <div>
        <h2 className="text-lg font-semibold">Export</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Download ledger and budget CSVs. Print/PDF: use your browser print on Reports.
        </p>
      </div>
      {error ? <ErrorBanner message={error} /> : null}
      {status ? <SuccessBanner message={status} /> : null}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="solar-btn-primary text-sm"
          disabled={Boolean(busy)}
          onClick={() => void exportTransactions()}
        >
          {busy === "all" ? "…" : "All transactions"}
        </button>
        <button
          type="button"
          className="solar-btn-ghost text-sm"
          disabled={Boolean(busy)}
          onClick={() => void exportTransactions("personal")}
        >
          Personal transactions
        </button>
        <button
          type="button"
          className="solar-btn-ghost text-sm"
          disabled={Boolean(busy)}
          onClick={() => void exportTransactions("business")}
        >
          Business transactions
        </button>
        <button
          type="button"
          className="solar-btn-ghost text-sm"
          disabled={Boolean(busy)}
          onClick={() => void exportBudgetPlan()}
        >
          Budget plans
        </button>
        {reportRows ? (
          <button
            type="button"
            className="solar-btn-ghost text-sm"
            onClick={exportReportSnapshot}
          >
            Report snapshot
          </button>
        ) : null}
      </div>
    </section>
  );
}
