import Link from "next/link";

import type { QuickFileReports } from "@/lib/finance-schemas";

import { QuickFileReportTable } from "./QuickFileReportTable";
import {
  buildQuickFileBalanceSheetItems,
  buildQuickFileProfitAndLossItems,
  hasQuickFileStatements,
} from "./quickfile-statement-rows";

type QuickFileStatementsProps = {
  reports: QuickFileReports | null | undefined;
  fallbackPl?: {
    turnover_gbp: number;
    expenses_gbp: number;
    net_profit_gbp: number;
  };
};

function periodLabel(fromDate: string, toDate: string) {
  return `${fromDate} to ${toDate}`;
}

export function QuickFileStatements({ reports, fallbackPl }: QuickFileStatementsProps) {
  if (!hasQuickFileStatements(reports)) {
    if (fallbackPl) {
      return (
        <article className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-6">
          <h3 className="text-lg font-semibold">Profit &amp; Loss Account</h3>
          <p className="mt-1 text-sm text-[var(--muted)]">
            From the latest business snapshot. Sync QuickFile on{" "}
            <Link href="/finance/connect" className="underline underline-offset-2">
              Connect banks
            </Link>{" "}
            for the live nominal breakdown.
          </p>
          <div className="mt-4">
            <QuickFileReportTable
              items={[
                { key: "turnover", label: "Turnover", amount: fallbackPl.turnover_gbp },
                { key: "expenses", label: "Less: Expenses", amount: fallbackPl.expenses_gbp },
                {
                  key: "net-profit",
                  label: "Net profit",
                  amount: fallbackPl.net_profit_gbp,
                  total: true,
                },
              ]}
            />
          </div>
        </article>
      );
    }
    return (
      <div className="rounded-2xl border border-dashed border-[var(--border)] bg-[var(--surface)] p-5 text-sm text-[var(--muted)]">
        No live QuickFile reports yet. Connect QuickFile on{" "}
        <Link href="/finance/connect" className="underline underline-offset-2">
          Connect banks
        </Link>{" "}
        and run a sync to pull profit &amp; loss and the balance sheet.
      </div>
    );
  }

  const pl = buildQuickFileProfitAndLossItems(reports!);
  const bs = buildQuickFileBalanceSheetItems(reports!);
  const syncedLabel = reports?.synced_at
    ? new Date(reports.synced_at).toLocaleDateString("en-GB")
    : null;
  const plMonthLabel =
    reports?.profit_and_loss_month &&
    periodLabel(reports.profit_and_loss_month.from_date, reports.profit_and_loss_month.to_date);
  const plYtdLabel =
    reports?.profit_and_loss_ytd &&
    periodLabel(reports.profit_and_loss_ytd.from_date, reports.profit_and_loss_ytd.to_date);

  return (
    <article className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-6">
      <header className="border-b border-[var(--border)] pb-4">
        <h3 className="text-lg font-semibold">Profit &amp; Loss Account</h3>
        {pl.subtitle ? <p className="mt-1 text-sm text-[var(--muted)]">{pl.subtitle}</p> : null}
      </header>
      <div className="py-4">
        <QuickFileReportTable
          items={pl.items}
          dualColumn={pl.dualColumn}
          monthColumnLabel={plMonthLabel || undefined}
          ytdColumnLabel={plYtdLabel || undefined}
        />
      </div>
      {bs.items.length > 0 ? (
        <>
          <header className="border-t border-[var(--border)] pt-6">
            <h3 className="text-lg font-semibold">Balance Sheet</h3>
            {bs.subtitle ? <p className="mt-1 text-sm text-[var(--muted)]">{bs.subtitle}</p> : null}
          </header>
          <div className="pt-4">
            <QuickFileReportTable items={bs.items} />
          </div>
        </>
      ) : null}
      {syncedLabel ? (
        <footer className="mt-6 border-t border-[var(--border)] pt-3 text-xs text-[var(--muted)]">
          Live QuickFile report · synced {syncedLabel}
        </footer>
      ) : null}
    </article>
  );
}
