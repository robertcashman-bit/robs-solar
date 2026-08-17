import { formatGbp } from "@/lib/money";

import type { QuickFileStatementRow } from "./quickfile-statement-rows";

type QuickFileReportTableProps = {
  items: QuickFileStatementRow[];
  dualColumn?: boolean;
  monthColumnLabel?: string;
  ytdColumnLabel?: string;
};

function lineLabel(item: QuickFileStatementRow) {
  if (item.nominalCode) {
    return `${item.nominalCode} ${item.label}`;
  }
  return item.label;
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
      <table className="w-full min-w-[20rem] border-collapse text-sm">
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
                <tr key={item.key}>
                  <td
                    colSpan={dualColumn ? 3 : 2}
                    className="pb-1 pt-4 font-semibold text-[var(--foreground)]"
                  >
                    {item.label}
                  </td>
                </tr>
              );
            }

            const labelClass = [
              "py-0.5 pr-4 align-top",
              item.indent ? "pl-8" : "",
              item.total ? "pt-2 font-semibold" : "",
            ]
              .filter(Boolean)
              .join(" ");
            const amountClass = [
              "py-0.5 pl-4 text-right align-top tabular-nums whitespace-nowrap",
              item.total ? "pt-2 font-semibold" : "",
            ]
              .filter(Boolean)
              .join(" ");
            const rowClass = item.total ? "border-t border-[var(--border)]" : "";

            if (dualColumn) {
              return (
                <tr key={item.key} className={rowClass}>
                  <td className={labelClass}>{lineLabel(item)}</td>
                  <td className={amountClass}>{formatGbp(item.monthAmount)}</td>
                  <td className={amountClass}>{formatGbp(item.ytdAmount)}</td>
                </tr>
              );
            }

            return (
              <tr key={item.key} className={rowClass}>
                <td className={labelClass}>{lineLabel(item)}</td>
                <td className={amountClass}>{formatGbp(item.amount)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
