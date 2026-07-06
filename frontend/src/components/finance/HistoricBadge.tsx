type HistoricBadgeProps = {
  title?: string;
};

export function HistoricBadge({ title = "Historic figure — will update when bank is connected" }: HistoricBadgeProps) {
  return (
    <sup
      className="ml-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded bg-amber-500/20 px-1 text-[10px] font-bold leading-none text-amber-700 dark:text-amber-300"
      title={title}
      aria-label={title}
    >
      H
    </sup>
  );
}
