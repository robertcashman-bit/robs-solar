import type { ReactNode } from "react";

import { formatGbp } from "@/lib/money";

export type OfWhichItem = {
  label: string;
  value: number | null | undefined;
  hint?: string;
  /** Hide rows with null/undefined/NaN, or optionally zero. */
  hideIfZero?: boolean;
};

type OfWhichBreakdownProps = {
  items: OfWhichItem[];
  /** Accessible name for the nested list. */
  ariaLabel?: string;
};

/**
 * Compact "of which" rows under a parent metric — subsets, not extra totals.
 */
export function OfWhichBreakdown({
  items,
  ariaLabel = "Of which breakdown",
}: OfWhichBreakdownProps) {
  const visible = items.filter((item) => {
    if (item.value == null || Number.isNaN(item.value)) return false;
    if (item.hideIfZero && item.value === 0) return false;
    return true;
  });
  if (visible.length === 0) return null;

  return (
    <ul
      className="mt-2 space-y-1.5 border-l-2 border-amber-400/40 pl-3"
      aria-label={ariaLabel}
    >
      {visible.map((item) => (
        <li key={item.label} className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
          <span className="text-xs text-[var(--muted)]">{item.label}</span>
          <span className="text-sm font-semibold tabular-nums tracking-tight">
            {formatGbp(item.value)}
          </span>
          {item.hint ? (
            <span className="basis-full text-[0.65rem] leading-snug text-[var(--muted)]">
              {item.hint}
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

type MetricWithOfWhichProps = {
  children: ReactNode;
  items: OfWhichItem[];
  ariaLabel?: string;
  className?: string;
};

/** Parent metric tile plus indented of-which list (subsets of the parent). */
export function MetricWithOfWhich({
  children,
  items,
  ariaLabel,
  className,
}: MetricWithOfWhichProps) {
  return (
    <div className={className}>
      {children}
      <OfWhichBreakdown items={items} ariaLabel={ariaLabel} />
    </div>
  );
}
