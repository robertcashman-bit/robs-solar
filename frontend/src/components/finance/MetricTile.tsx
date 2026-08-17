import { formatGbp } from "@/lib/money";

type MetricTileProps = {
  label: string;
  value: number | null | undefined;
  hint?: string;
  warning?: boolean;
  positive?: boolean;
  format?: "currency" | "number";
};

export function MetricTile({ label, value, hint, warning, positive, format = "currency" }: MetricTileProps) {
  const tone = warning
    ? "border-amber-400/40 bg-amber-500/10"
    : positive
      ? "border-emerald-400/40 bg-emerald-500/10"
      : "border-[var(--border)] bg-[var(--surface-elevated)]";

  const display =
    format === "currency"
      ? formatGbp(value)
      : value == null || Number.isNaN(value)
        ? "—"
        : String(value);

  return (
    <div className={`rounded-2xl border p-4 ${tone}`}>
      <p className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums tracking-tight">{display}</p>
      {hint ? <p className="mt-1 text-xs text-[var(--muted)]">{hint}</p> : null}
    </div>
  );
}
