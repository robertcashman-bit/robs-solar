import type { FinanceInsight } from "@/lib/finance-schemas";

const severityStyles: Record<string, string> = {
  info: "border-sky-400/35 bg-sky-500/10 text-sky-950 dark:text-sky-100",
  warning: "border-amber-400/35 bg-amber-500/10 text-amber-950 dark:text-amber-100",
  critical: "border-rose-400/35 bg-rose-500/10 text-rose-950 dark:text-rose-100",
};

export function InsightCard({ insight }: { insight: FinanceInsight }) {
  return (
    <div className={`rounded-xl border px-4 py-3 text-sm ${severityStyles[insight.severity] ?? severityStyles.info}`}>
      <p className="font-semibold">{insight.title}</p>
      <p className="mt-1 opacity-90">{insight.message}</p>
      <p className="mt-2 text-xs uppercase tracking-wide opacity-70">{insight.category}</p>
    </div>
  );
}
