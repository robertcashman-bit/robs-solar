type StatusBadgeTone = "positive" | "negative" | "warning" | "neutral";

type StatusBadgeProps = {
  label: string;
  tone?: StatusBadgeTone;
  /** When true, shows a coloured dot alongside the label (not colour-only — text is always present). */
  showDot?: boolean;
  /** Optional accessible name when the visible label alone is ambiguous. */
  ariaLabel?: string;
};

const toneStyles: Record<StatusBadgeTone, { wrapper: string; dot: string }> = {
  positive: {
    wrapper: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
    dot: "bg-emerald-500",
  },
  negative: {
    wrapper: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
    dot: "bg-red-500",
  },
  warning: {
    wrapper: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
    dot: "bg-amber-500",
  },
  neutral: {
    wrapper: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-300",
    dot: "bg-zinc-400",
  },
};

export function StatusBadge({ label, tone = "neutral", showDot = true }: StatusBadgeProps) {
  const styles = toneStyles[tone];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${styles.wrapper}`}
      data-status={label}
    >
      {showDot ? <span className={`h-1.5 w-1.5 rounded-full ${styles.dot}`} aria-hidden="true" /> : null}
      <span>{label}</span>
    </span>
  );
}
