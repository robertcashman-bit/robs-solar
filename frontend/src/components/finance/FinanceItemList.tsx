import { FinanceAmount } from "@/components/finance/FinanceAmount";
import { HistoricBadge } from "@/components/finance/HistoricBadge";
import type { FinanceAmountRole } from "@/lib/money";

export type FinanceItem = {
  key: string;
  label: string;
  nominalCode?: string | null;
  detail?: string;
  amount?: number | null;
  role?: FinanceAmountRole;
  monthAmount?: number | null;
  monthRole?: FinanceAmountRole;
  ytdAmount?: number | null;
  ytdRole?: FinanceAmountRole;
  historic?: boolean;
  total?: boolean;
  sectionHeader?: boolean;
  indent?: boolean;
};

type FinanceItemListProps = {
  title: string;
  subtitle?: string;
  items: FinanceItem[];
  dualColumn?: boolean;
  monthColumnLabel?: string;
  ytdColumnLabel?: string;
  footer?: React.ReactNode;
};

export function FinanceItemList({
  title,
  subtitle,
  items,
  dualColumn = false,
  monthColumnLabel = "Month",
  ytdColumnLabel = "YTD",
  footer,
}: FinanceItemListProps) {
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

      <ul className={dualColumn ? "mt-1" : "mt-3 divide-y divide-[var(--border)]"}>
        {items.map((item) => {
          const rowClass = item.total
            ? "border-t border-[var(--border)] pt-2 font-semibold"
            : "";
          const labelClass = [
            item.total ? "text-base font-semibold" : "",
            item.sectionHeader ? "pt-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]" : "",
            item.indent ? "pl-4 text-[var(--muted)]" : "",
          ]
            .filter(Boolean)
            .join(" ");

          if (item.sectionHeader) {
            return (
              <li
                key={item.key}
                className={`pt-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)] ${
                  dualColumn ? "grid grid-cols-[1fr_auto_auto]" : ""
                }`.trim()}
              >
                <span className={dualColumn ? "col-span-3" : undefined}>{item.label}</span>
              </li>
            );
          }

          if (dualColumn) {
            return (
              <li
                key={item.key}
                className={`grid grid-cols-[1fr_auto_auto] items-baseline gap-x-4 py-2 text-sm ${rowClass}`.trim()}
              >
                <span className={`flex items-baseline gap-1 ${labelClass}`.trim()}>
                  {item.label}
                  {item.detail ? (
                    <span className="font-normal text-[var(--muted)]"> · {item.detail}</span>
                  ) : null}
                  {item.historic ? <HistoricBadge /> : null}
                </span>
                <span className="min-w-[6.5rem] text-right">
                  <FinanceAmount
                    value={item.monthAmount}
                    role={item.monthRole ?? item.role ?? "signed"}
                    className="font-medium"
                  />
                </span>
                <span className="min-w-[6.5rem] text-right">
                  <FinanceAmount
                    value={item.ytdAmount}
                    role={item.ytdRole ?? item.role ?? "signed"}
                    className="font-medium"
                  />
                </span>
              </li>
            );
          }

          return (
            <li
              key={item.key}
              className={`flex items-baseline justify-between gap-4 py-2.5 text-sm ${rowClass}`.trim()}
            >
              <span className={`min-w-0 ${labelClass}`.trim()}>
                {item.label}
                {item.detail ? (
                  <span className="font-normal text-[var(--muted)]"> · {item.detail}</span>
                ) : null}
                {item.historic ? <HistoricBadge /> : null}
              </span>
              <FinanceAmount
                value={item.amount}
                role={item.role ?? "signed"}
                className="shrink-0 font-medium"
              />
            </li>
          );
        })}
      </ul>

      {footer ? <footer className="mt-4 border-t border-[var(--border)] pt-3 text-sm">{footer}</footer> : null}
    </article>
  );
}
