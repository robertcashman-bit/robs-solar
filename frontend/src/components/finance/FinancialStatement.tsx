import { FinanceAmount } from "@/components/finance/FinanceAmount";
import { HistoricBadge } from "@/components/finance/HistoricBadge";
import type { FinanceAmountRole } from "@/lib/money";

export type StatementRow = {
  kind: "header" | "row" | "subtotal" | "total";
  label: string;
  amount?: number | null;
  amountRole?: FinanceAmountRole;
  monthAmount?: number | null;
  monthRole?: FinanceAmountRole;
  ytdAmount?: number | null;
  ytdRole?: FinanceAmountRole;
  indent?: 0 | 1 | 2;
  historic?: boolean;
};

type FinancialStatementProps = {
  title: string;
  subtitle?: string;
  dualColumn?: boolean;
  monthColumnLabel?: string;
  ytdColumnLabel?: string;
  rows: StatementRow[];
  footer?: React.ReactNode;
};

function indentClass(indent: 0 | 1 | 2 | undefined) {
  if (indent === 1) return "pl-4";
  if (indent === 2) return "pl-8";
  return "";
}

function AmountCell({
  value,
  role = "signed",
}: {
  value: number | null | undefined;
  role?: FinanceAmountRole;
}) {
  return (
    <span className="block min-w-[6.5rem] text-right">
      <FinanceAmount value={value} role={role} className="font-medium" />
    </span>
  );
}

export function FinancialStatement({
  title,
  subtitle,
  dualColumn = false,
  monthColumnLabel = "Month",
  ytdColumnLabel = "YTD",
  rows,
  footer,
}: FinancialStatementProps) {
  return (
    <article className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5">
      <header>
        <h3 className="text-base font-semibold tracking-tight">{title}</h3>
        {subtitle ? <p className="mt-1 text-sm text-[var(--muted)]">{subtitle}</p> : null}
      </header>

      {dualColumn ? (
        <div className="mt-4 grid grid-cols-[1fr_auto_auto] gap-x-4 border-b border-[var(--border)] pb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
          <span />
          <span className="min-w-[6.5rem] text-right">{monthColumnLabel}</span>
          <span className="min-w-[6.5rem] text-right">{ytdColumnLabel}</span>
        </div>
      ) : null}

      <dl className="mt-2 space-y-0">
        {rows.map((row, index) => {
          if (row.kind === "header") {
            return (
              <div
                key={`${row.label}-${index}`}
                className="border-t border-[var(--border)] pt-3 first:border-t-0 first:pt-0"
              >
                <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                  {row.label}
                </dt>
              </div>
            );
          }

          const rowClass = [
            "grid items-baseline gap-x-4 py-1.5 text-sm",
            dualColumn ? "grid-cols-[1fr_auto_auto]" : "grid-cols-[1fr_auto]",
            row.kind === "subtotal" || row.kind === "total"
              ? "border-t border-[var(--border)] pt-2 font-semibold"
              : "",
            indentClass(row.indent),
          ]
            .filter(Boolean)
            .join(" ");

          const labelClass =
            row.kind === "total" ? "text-base font-semibold" : row.kind === "subtotal" ? "font-semibold" : "";

          return (
            <div key={`${row.label}-${index}`} className={rowClass}>
              <dt className={`flex items-baseline gap-1 ${labelClass}`.trim()}>
                <span>{row.label}</span>
                {row.historic ? <HistoricBadge /> : null}
              </dt>
              {dualColumn ? (
                <>
                  <AmountCell value={row.monthAmount} role={row.monthRole ?? row.amountRole ?? "signed"} />
                  <AmountCell value={row.ytdAmount} role={row.ytdRole ?? row.amountRole ?? "signed"} />
                </>
              ) : (
                <AmountCell value={row.amount} role={row.amountRole ?? "signed"} />
              )}
            </div>
          );
        })}
      </dl>

      {footer ? <footer className="mt-4 border-t border-[var(--border)] pt-3 text-sm">{footer}</footer> : null}
    </article>
  );
}
