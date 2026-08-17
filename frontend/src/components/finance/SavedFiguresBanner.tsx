type SavedFiguresBannerProps = {
  refreshing: boolean;
  generatedAt?: string | null;
  cached?: boolean;
  quickfileSyncedAt?: string | null;
  lunchflowSyncedAt?: string | null;
};

function formatStamp(value?: string | null): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleString("en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Last-updated stamp, plus a note while live sync is still running. */
export function SavedFiguresBanner({
  refreshing,
  generatedAt,
  cached,
  quickfileSyncedAt,
  lunchflowSyncedAt,
}: SavedFiguresBannerProps) {
  const updated = formatStamp(generatedAt);
  const quickfile = formatStamp(quickfileSyncedAt);
  const lunchflow = formatStamp(lunchflowSyncedAt);
  if (!refreshing && !updated && !quickfile && !lunchflow) {
    return null;
  }
  return (
    <div className="mb-3 space-y-1 text-sm text-[var(--muted)]">
      {updated ? (
        <p>
          Data updated: {updated}
          {cached ? " (saved figures)" : ""}
        </p>
      ) : null}
      {quickfile ? <p>QuickFile synced: {quickfile}</p> : null}
      {lunchflow ? <p>Lunch Flow synced: {lunchflow}</p> : null}
      {refreshing ? <p>Showing saved figures — updating live balances…</p> : null}
    </div>
  );
}
