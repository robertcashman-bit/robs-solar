import { FinanceAmount } from "@/components/finance/FinanceAmount";
import type { FinanceItem } from "@/components/finance/FinanceItemList";
import type { FinanceAmountRole } from "@/lib/money";

type QuickFileReportTableProps = {
  items: FinanceItem[];
  dualColumn?: boolean;
  monthColumnLabel?: string;
  ytdColumnLabel?: string;
};

function lineLabel(item: FinanceItem) {
  if (item.nominalCode) {
    return `${item.nominalCode} ${item.label}`;
  }
  return item.label;
}

function amountRole(
  value: number | null | undefined,
  role: FinanceAmountRole | undefined,
): FinanceAmountRole {
  if (value != null && value < 0) {
    return "signed";
  }
  return role ?? "signed";
}

function AmountCell({
  value,
  role,
}: {
  value: number | null | undefined;
  role?: FinanceAmountRole;
}) {
  return (
    <FinanceAmount
      value={value}
      role={amountRole(value, role)}
      className="font-medium"
    />
  );
}

export function QuickFileReportTable({
  items,
  dualColumn = false,
  monthColumnLabel = "This period",
  ytdColumnLabel = "Year to date",
}: QuickFileReportTableProps) {
  if (items.length === 0) return null;

  return (
    <div className="overflow-x-auto">
      <table className="quickfile-report w-full min-w-[20rem] border-collapse text-sm">
        {dualColumn ? (
          <thead>
            <tr className="border-b border-[var(--border)] text-xs text-[var(--muted)]">
              <th className="pb-2 pr-4 text-left font-normal" scope="col" />
              <th className="min-w-[7rem] pb-2 pl-4 text-right font-normal" scope="col">
                {monthColumnLabel}
              </th>
              <th className="min-w-[7rem] pb-2 pl-4 text-right font-normal" scope="col">
                {ytdColumnLabel}
              </th>
            </tr>
          </thead>
        ) : null}
        <tbody>
          {items.map((item) => {
            if (item.sectionHeader) {
              return (
                <tr key={item.key} className="quickfile-report-section">
                  <td
                    colSpan={dualColumn ? 3 : 2}
                    className="pt-4 pb-1 font-semibold text-[var(--foreground)]"
                  >
                    {item.label}
                  </td>
                </tr>
              );
            }

            const rowClass = [
              item.total ? "quickfile-report-total border-t border-[var(--border)]" : "",
              item.indent ? "quickfile-report-line" : "",
            ]
              .filter(Boolean)
              .join(" ");

            const labelCellClass = [
              "py-0.5 pr-4 align-top",
              item.indent ? "pl-8 text-[var(--foreground)]" : "",
              item.total ? "pt-2 font-semibold" : "",
            ]
              .filter(Boolean)
              .join(" ");

            const amountCellClass = [
              "py-0.5 pl-4 text-right align-top whitespace-nowrap",
              item.total ? "pt-2 font-semibold" : "",
            ]
              .filter(Boolean)
              .join(" ");

            if (dualColumn) {
              return (
                <tr key={item.key} className={rowClass}>
                  <td className={labelCellClass}>{lineLabel(item)}</td>
                  <td className={amountCellClass}>
                    <AmountCell value={item.monthAmount} role={item.monthRole ?? item.role} />
                  </td>
                  <td className={amountCellClass}>
                    <AmountCell value={item.ytdAmount} role={item.ytdRole ?? item.role} />
                  </td>
                </tr>
              );
            }

            return (
              <tr key={item.key} className={rowClass}>
                <td className={labelCellClass}>{lineLabel(item)}</td>
                <td className={amountCellClass}>
                  <AmountCell value={item.amount} role={item.role} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
