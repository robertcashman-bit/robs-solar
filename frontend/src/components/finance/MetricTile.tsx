import { HistoricBadge } from "@/components/finance/HistoricBadge";
import { formatFinanceGbp, formatGbp, type FinanceAmountRole } from "@/lib/money";

type MetricTileProps = {
  label: string;
  value: number | null | undefined;
  hint?: string;
  warning?: boolean;
  positive?: boolean;
  historic?: boolean;
  format?: "currency" | "number";
  /** When set, shows explicit + (credit/asset) or − (debit/debt) prefix. */
  amountRole?: FinanceAmountRole;
};

export function MetricTile({
  label,
  value,
  hint,
  warning,
  positive,
  historic,
  format = "currency",
  amountRole,
}: MetricTileProps) {
  const tone = warning
    ? "border-amber-400/40 bg-amber-500/10"
    : positive
      ? "border-emerald-400/40 bg-emerald-500/10"
      : amountRole === "debt" || amountRole === "outflow"
        ? "border-red-400/35 bg-red-500/10"
        : amountRole === "asset" || amountRole === "inflow"
          ? "border-emerald-400/40 bg-emerald-500/10"
          : "border-[var(--border)] bg-[var(--surface-elevated)]";

  let display: string;
  let amountClass = "";

  if (format === "number") {
    display =
      value == null || Number.isNaN(value) ? "—" : String(value);
  } else if (amountRole) {
    const formatted = formatFinanceGbp(value, amountRole);
    display = formatted.text;
    amountClass = formatted.className;
  } else {
    display = formatGbp(value);
    if (positive) {
      amountClass = "text-emerald-600 dark:text-emerald-400";
    } else if (warning) {
      amountClass = "text-amber-600 dark:text-amber-400";
    }
  }

  const roleHint =
    amountRole === "asset" || amountRole === "inflow"
      ? "Credit (+)"
      : amountRole === "debt" || amountRole === "outflow"
        ? "Debit (−)"
        : amountRole === "signed"
          ? "Net (+/−)"
          : null;

  return (
    <div className={`rounded-2xl border p-4 ${tone}`}>
      <p className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
        {label}
        {historic ? <HistoricBadge /> : null}
      </p>
      <p className={`mt-1 text-2xl font-bold tabular-nums tracking-tight ${amountClass}`}>
        {display}
      </p>
      {roleHint ? <p className="mt-0.5 text-[10px] uppercase tracking-wide text-[var(--muted)]">{roleHint}</p> : null}
      {hint ? <p className="mt-1 text-xs text-[var(--muted)]">{hint}</p> : null}
    </div>
  );
}
