type SavedFiguresBannerProps = {
  refreshing: boolean;
};

/** Shown while stored Neon data is on screen and live sync is still running. */
export function SavedFiguresBanner({ refreshing }: SavedFiguresBannerProps) {
  if (!refreshing) {
    return null;
  }
  return (
    <p className="mb-3 text-sm text-[var(--muted)]">
      Showing saved figures — updating live balances…
    </p>
  );
}
