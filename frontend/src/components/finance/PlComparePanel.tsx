"use client";

import { useEffect, useState } from "react";

import { MetricTile } from "@/components/finance/MetricTile";
import { apiClient } from "@/lib/api-client";
import { formatGbp } from "@/lib/money";
import { z } from "zod";

const pnlCompareRowSchema = z.object({
  key: z.string(),
  label: z.string(),
  date_from: z.string().nullable().optional(),
  date_to: z.string().nullable().optional(),
  income_gbp: z.number().nullable().optional(),
  spending_gbp: z.number().nullable().optional(),
  surplus_gbp: z.number().nullable().optional(),
  transaction_count: z.number().optional().default(0),
  coverage_note: z.string().optional().default(""),
  empty: z.boolean().optional().default(false),
  compare_label: z.string().optional(),
  compare_date_from: z.string().nullable().optional(),
  compare_date_to: z.string().nullable().optional(),
  compare_income_gbp: z.number().nullable().optional(),
  compare_spending_gbp: z.number().nullable().optional(),
  compare_surplus_gbp: z.number().nullable().optional(),
  compare_transaction_count: z.number().optional().default(0),
  compare_coverage_note: z.string().optional().default(""),
  compare_empty: z.boolean().optional().default(false),
  income_change_gbp: z.number().nullable().optional(),
  spending_change_gbp: z.number().nullable().optional(),
  surplus_change_gbp: z.number().nullable().optional(),
});

const pnlCompareSchema = z.object({
  scope: z.string(),
  as_of: z.string(),
  rows: z.array(pnlCompareRowSchema),
});

type PnlCompare = z.infer<typeof pnlCompareSchema>;
type PnlCompareRow = z.infer<typeof pnlCompareRowSchema>;

type PlComparePanelProps = {
  scope: "personal" | "business";
  title?: string;
};

function signedGbp(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  const formatted = formatGbp(Math.abs(value));
  if (value > 0) return `+${formatted}`;
  if (value < 0) return `−${formatted}`;
  return formatted;
}

/** Prior-window empty notes reuse "No stored transactions in 6 months" — too easy
 * to read as the current window being empty while figures are on screen. */
function compareEmptyHint(row: PnlCompareRow): string {
  const label = (row.compare_label || "comparison period").trim();
  const lowered = label.toLowerCase();
  // Avoid "No prior prior 6 months…" when compare_label already starts with Prior.
  if (lowered.startsWith("prior ")) {
    return `No ${lowered} data to compare yet.`;
  }
  return `No prior ${lowered} data to compare yet.`;
}

export function PlComparePanel({ scope, title }: PlComparePanelProps) {
  const [data, setData] = useState<PnlCompare | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const raw = await apiClient.get<unknown>(`/finance/pnl-compare?scope=${scope}`);
        if (cancelled) return;
        setData(pnlCompareSchema.parse(raw));
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setData(null);
        setError(err instanceof Error ? err.message : "P&L compare unavailable");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [scope]);

  return (
    <section aria-label={title ?? "Profit and loss compare"}>
      <h2 className="solar-section-title">{title ?? "Profit & loss compare"}</h2>
      <p className="mt-1 text-sm text-[var(--muted)]">
        From stored transactions only. Empty windows are labelled — nothing is invented.
      </p>
      {error ? <p className="mt-3 text-sm text-amber-800 dark:text-amber-200">{error}</p> : null}
      {!error && !data ? (
        <p className="mt-3 text-sm text-[var(--muted)]">Loading P&amp;L compare…</p>
      ) : null}
      {data ? (
        <div className="mt-4 space-y-4">
          {data.rows.map((row) => (
            <div
              key={row.key}
              className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="font-semibold">{row.label}</h3>
                <p className="text-xs text-[var(--muted)]">
                  {row.date_from && row.date_to ? `${row.date_from} → ${row.date_to}` : null}
                  {row.compare_date_from && row.compare_date_to
                    ? ` · vs ${row.compare_date_from} → ${row.compare_date_to}`
                    : null}
                </p>
              </div>
              {row.empty ? (
                <p className="mt-2 text-sm text-[var(--muted)]">
                  {row.coverage_note || "No stored transactions in this window."}
                </p>
              ) : (
                <div className="mt-3 grid gap-3 sm:grid-cols-3">
                  <MetricTile
                    label="Income"
                    value={row.income_gbp}
                    positive
                    hint={
                      row.income_change_gbp == null
                        ? row.compare_empty
                          ? compareEmptyHint(row)
                          : undefined
                        : `${signedGbp(row.income_change_gbp)} vs ${row.compare_label}`
                    }
                  />
                  <MetricTile
                    label="Spending"
                    value={row.spending_gbp}
                    hint={
                      row.spending_change_gbp == null
                        ? row.compare_empty
                          ? compareEmptyHint(row)
                          : undefined
                        : `${signedGbp(row.spending_change_gbp)} vs ${row.compare_label}`
                    }
                  />
                  <MetricTile
                    label="Surplus"
                    value={row.surplus_gbp}
                    positive={(row.surplus_gbp ?? 0) >= 0}
                    warning={(row.surplus_gbp ?? 0) < 0}
                    hint={
                      row.surplus_change_gbp == null
                        ? row.compare_empty
                          ? compareEmptyHint(row)
                          : undefined
                        : `${signedGbp(row.surplus_change_gbp)} vs ${row.compare_label}`
                    }
                  />
                </div>
              )}
              {!row.empty && row.coverage_note ? (
                <p className="mt-2 text-xs text-amber-800 dark:text-amber-200">{row.coverage_note}</p>
              ) : null}
              {!row.empty && row.compare_empty ? (
                <p className="mt-2 text-xs text-[var(--muted)]">{compareEmptyHint(row)}</p>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
