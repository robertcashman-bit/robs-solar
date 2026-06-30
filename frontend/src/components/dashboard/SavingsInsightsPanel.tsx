"use client";

import Link from "next/link";

import type { SavingsInsight } from "@/lib/savings-insights";
import { AlertIcon, ChartIcon } from "@/components/shared/icons";

const severityStyles: Record<
  SavingsInsight["severity"],
  { border: string; icon: string; bg: string }
> = {
  positive: {
    border: "border-emerald-400/35",
    icon: "text-emerald-600 dark:text-emerald-400",
    bg: "bg-emerald-500/8",
  },
  warning: {
    border: "border-amber-400/40",
    icon: "text-amber-600 dark:text-amber-400",
    bg: "bg-amber-500/10",
  },
  action: {
    border: "border-sky-400/40",
    icon: "text-sky-600 dark:text-sky-400",
    bg: "bg-sky-500/10",
  },
  neutral: {
    border: "border-[var(--border)]",
    icon: "text-[var(--muted)]",
    bg: "bg-[var(--surface)]",
  },
};

type SavingsInsightsPanelProps = {
  insights: SavingsInsight[];
};

export function SavingsInsightsPanel({ insights }: SavingsInsightsPanelProps) {
  return (
    <section aria-label="Savings insights" className="solar-card">
      <div className="mb-4 flex items-center gap-2">
        <ChartIcon size={18} className="text-[var(--solar)]" />
        <h3 className="solar-section-title">What to do next</h3>
      </div>
      <ul className="space-y-3">
        {insights.map((insight) => {
          const style = severityStyles[insight.severity];
          return (
            <li
              key={insight.id}
              className={`rounded-xl border p-4 ${style.border} ${style.bg}`}
            >
              <div className="flex gap-3">
                <AlertIcon size={18} className={`mt-0.5 shrink-0 ${style.icon}`} />
                <div className="min-w-0 flex-1">
                  <p className="font-semibold leading-snug">{insight.title}</p>
                  <p className="mt-1 text-sm text-[var(--muted)]">{insight.body}</p>
                  {insight.actionHref && insight.actionLabel ? (
                    <Link
                      href={insight.actionHref}
                      className="mt-2 inline-flex text-sm font-medium text-[var(--solar-dark)] underline-offset-2 hover:underline dark:text-amber-400"
                    >
                      {insight.actionLabel} →
                    </Link>
                  ) : null}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
