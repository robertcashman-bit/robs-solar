import Link from "next/link";

import {
  buildQuickFileBalanceSheetItems,
  buildQuickFileProfitAndLossItems,
  hasQuickFileStatements,
} from "@/components/finance/quickfile-statement-rows";
import { filterZeroFinanceItems } from "@/components/finance/finance-item-utils";
import type { FinanceItem } from "@/components/finance/FinanceItemList";
import { QuickFileReportTable } from "@/components/finance/QuickFileReportTable";
import type { QuickFileReports } from "@/lib/finance-schemas";
import { formatQuickFilePeriod } from "@/lib/money";

type QuickFileFallbackPl = {
  turnover_gbp: number;
  expenses_gbp: number;
  net_profit_gbp: number;
};

type QuickFileStatementsProps = {
  reports: QuickFileReports | null | undefined;
  fallbackPl?: QuickFileFallbackPl;
  compact?: boolean;
  sections?: Array<"pl" | "bs">;
  hideZero?: boolean;
  /** Single document: P&L account first, balance sheet underneath (QuickFile layout). */
  variant?: "stacked" | "document";
};

function applyHideZero(items: FinanceItem[], hideZero: boolean, dualColumn = false) {
  if (!hideZero) return items;
  return filterZeroFinanceItems(items, dualColumn);
}

function QuickFileDocument({
  plItems,
  plSubtitle,
  plDualColumn,
  plMonthLabel,
  plYtdLabel,
  bsItems,
  bsSubtitle,
  syncedLabel,
}: {
  plItems: FinanceItem[];
  plSubtitle: string;
  plDualColumn: boolean;
  plMonthLabel?: string;
  plYtdLabel?: string;
  bsItems: FinanceItem[];
  bsSubtitle: string;
  syncedLabel: string | null;
}) {
  return (
    <article className="quickfile-report-document rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-6">
      <header className="border-b border-[var(--border)] pb-4 text-center sm:text-left">
        <h3 className="text-lg font-semibold text-[var(--foreground)]">Profit &amp; Loss Account</h3>
        {plSubtitle ? <p className="mt-1 text-sm text-[var(--muted)]">{plSubtitle}</p> : null}
      </header>
      <div className="py-4">
        <QuickFileReportTable
          items={plItems}
          dualColumn={plDualColumn}
          monthColumnLabel={plMonthLabel}
          ytdColumnLabel={plYtdLabel}
        />
      </div>

      {bsItems.length > 0 ? (
        <>
          <header className="border-t border-[var(--border)] pt-6 text-center sm:text-left">
            <h3 className="text-lg font-semibold text-[var(--foreground)]">Balance Sheet</h3>
            {bsSubtitle ? <p className="mt-1 text-sm text-[var(--muted)]">{bsSubtitle}</p> : null}
          </header>
          <div className="pt-4">
            <QuickFileReportTable items={bsItems} />
          </div>
        </>
      ) : null}

      {syncedLabel ? (
        <footer className="mt-6 border-t border-[var(--border)] pt-3 text-center text-xs text-[var(--muted)] sm:text-left">
          QuickFile report · synced {syncedLabel}
        </footer>
      ) : null}
    </article>
  );
}

function FallbackDocument({ fallback, hideZero }: { fallback: QuickFileFallbackPl; hideZero: boolean }) {
  const items = applyHideZero(
    [
      { key: "turnover", label: "Turnover", amount: fallback.turnover_gbp, role: "inflow" },
      {
        key: "expenses",
        label: "Less: Expenses",
        amount: fallback.expenses_gbp,
        role: "outflow",
      },
      {
        key: "net-profit",
        label: "Net profit",
        amount: fallback.net_profit_gbp,
        role: "signed",
        total: true,
      },
    ],
    hideZero,
  );
  if (items.length === 0) return null;

  return (
    <article className="quickfile-report-document rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-6">
      <header className="text-center sm:text-left">
        <h3 className="text-lg font-semibold text-[var(--foreground)]">Profit &amp; Loss Account</h3>
        <p className="mt-1 text-sm text-[var(--muted)]">
          From latest business snapshot — sync QuickFile for full detail
        </p>
      </header>
      <div className="mt-4">
        <QuickFileReportTable items={items} />
      </div>
    </article>
  );
}

export function QuickFileStatements({
  reports,
  fallbackPl,
  compact = false,
  sections = ["pl", "bs"],
  hideZero = true,
  variant = "stacked",
}: QuickFileStatementsProps) {
  const showPl = sections.includes("pl");
  const showBs = sections.includes("bs");
  const hasReports = hasQuickFileStatements(reports);

  if (!hasReports) {
    if (fallbackPl && showPl) {
      return (
        <div className={compact ? "space-y-4" : "space-y-6"}>
          <FallbackDocument fallback={fallbackPl} hideZero={hideZero} />
        </div>
      );
    }
    return (
      <div className="rounded-2xl border border-dashed border-[var(--border)] bg-[var(--surface)] p-5 text-sm text-[var(--muted)]">
        No QuickFile reports yet. Connect QuickFile in{" "}
        <Link href="/settings" className="underline">
          Settings
        </Link>{" "}
        and run a sync to pull profit &amp; loss and balance sheet data.
      </div>
    );
  }

  const pl = showPl ? buildQuickFileProfitAndLossItems(reports!) : null;
  const bs = showBs ? buildQuickFileBalanceSheetItems(reports!) : null;
  const plItems = pl
    ? pl.fullBreakdown || !hideZero
      ? pl.items
      : applyHideZero(pl.items, hideZero, pl.dualColumn)
    : [];
  const bsItems = bs
    ? bs.fullBreakdown || !hideZero
      ? bs.items
      : applyHideZero(bs.items, hideZero)
    : [];
  const syncedLabel = reports?.synced_at
    ? new Date(reports.synced_at).toLocaleDateString("en-GB")
    : null;

  const plMonthLabel =
    reports?.profit_and_loss_month &&
    formatQuickFilePeriod(
      reports.profit_and_loss_month.from_date,
      reports.profit_and_loss_month.to_date,
    );
  const plYtdLabel =
    reports?.profit_and_loss_ytd &&
    formatQuickFilePeriod(
      reports.profit_and_loss_ytd.from_date,
      reports.profit_and_loss_ytd.to_date,
    );

  if (variant === "document") {
    if (plItems.length === 0 && bsItems.length === 0) {
      return (
        <div className="rounded-2xl border border-dashed border-[var(--border)] bg-[var(--surface)] p-5 text-sm text-[var(--muted)]">
          No QuickFile figures to display for this period.
        </div>
      );
    }
    return (
      <QuickFileDocument
        plItems={plItems}
        plSubtitle={pl?.subtitle ?? ""}
        plDualColumn={pl?.dualColumn ?? false}
        plMonthLabel={plMonthLabel || undefined}
        plYtdLabel={plYtdLabel || undefined}
        bsItems={bsItems}
        bsSubtitle={bs?.subtitle ?? ""}
        syncedLabel={syncedLabel}
      />
    );
  }

  return (
    <div className={compact ? "space-y-4" : "space-y-6"}>
      {showPl && plItems.length > 0 ? (
        <article className="quickfile-report-document rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-6">
          <header className="text-center sm:text-left">
            <h3 className="text-lg font-semibold text-[var(--foreground)]">Profit &amp; Loss Account</h3>
            {pl?.subtitle ? <p className="mt-1 text-sm text-[var(--muted)]">{pl.subtitle}</p> : null}
          </header>
          <div className="mt-4">
            <QuickFileReportTable
              items={plItems}
              dualColumn={pl?.dualColumn}
              monthColumnLabel={plMonthLabel || undefined}
              ytdColumnLabel={plYtdLabel || undefined}
            />
          </div>
        </article>
      ) : null}
      {showBs && bsItems.length > 0 ? (
        <article className="quickfile-report-document rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-6">
          <header className="text-center sm:text-left">
            <h3 className="text-lg font-semibold text-[var(--foreground)]">Balance Sheet</h3>
            {bs?.subtitle ? <p className="mt-1 text-sm text-[var(--muted)]">{bs.subtitle}</p> : null}
          </header>
          <div className="mt-4">
            <QuickFileReportTable items={bsItems} />
          </div>
          {syncedLabel ? (
            <footer className="mt-6 border-t border-[var(--border)] pt-3 text-xs text-[var(--muted)]">
              QuickFile report · synced {syncedLabel}
            </footer>
          ) : null}
        </article>
      ) : null}
    </div>
  );
}
