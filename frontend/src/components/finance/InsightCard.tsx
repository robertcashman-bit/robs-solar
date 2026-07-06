import Link from "next/link";

import type { FinanceInsight } from "@/lib/finance-schemas";
import { insightCategoryHref, insightCategoryLabel } from "@/lib/finance-insight-links";

const severityStyles: Record<string, string> = {
  info: "border-sky-400/35 bg-sky-500/10 text-sky-950 dark:text-sky-100",
  warning: "border-amber-400/35 bg-amber-500/10 text-amber-950 dark:text-amber-100",
  critical: "border-rose-400/35 bg-rose-500/10 text-rose-950 dark:text-rose-100",
};

type InsightCardProps = {
  insight: FinanceInsight;
  prominent?: boolean;
};

export function InsightCard({ insight, prominent = false }: InsightCardProps) {
  const href = insightCategoryHref(insight.category);
  const label = insightCategoryLabel(insight.category);

  return (
    <div
      className={`rounded-xl border text-sm ${severityStyles[insight.severity] ?? severityStyles.info} ${
        prominent ? "px-5 py-4" : "px-4 py-3"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className={`font-semibold ${prominent ? "text-base" : ""}`}>{insight.title}</p>
        <span className="rounded-full bg-black/5 px-2 py-0.5 text-xs font-medium dark:bg-white/10">
          {label}
        </span>
      </div>
      <p className={`mt-2 opacity-90 ${prominent ? "text-[15px]" : ""}`}>{insight.message}</p>
      <Link href={href} className="mt-3 inline-block text-sm font-medium underline underline-offset-2">
        View {label.toLowerCase()} →
      </Link>
    </div>
  );
}
