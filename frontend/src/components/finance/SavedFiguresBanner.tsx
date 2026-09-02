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
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function freshnessLabel(value?: string | null): string {
  if (!value) return "never synced";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "unknown";
  const ageMs = Date.now() - parsed.getTime();
  if (ageMs < 15 * 60 * 1000) return "up to date";
  if (ageMs < 24 * 60 * 60 * 1000) return "a few hours old";
  return "needs a Refresh";
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
          {cached
            ? " — last saved overview (may be stale until live sync finishes)"
            : " — live overview"}
        </p>
      ) : null}
      {quickfile ? (
        <p>
          QuickFile (Defence Legal books): {quickfile} — {freshnessLabel(quickfileSyncedAt)}
        </p>
      ) : (
        <p>QuickFile (Defence Legal books): not synced yet</p>
      )}
      {lunchflow ? (
        <p>
          Lunch Flow (personal banks): {lunchflow} — {freshnessLabel(lunchflowSyncedAt)}
        </p>
      ) : (
        <p>Lunch Flow (personal banks): not synced yet</p>
      )}
      {refreshing ? (
        <p>Showing last saved figures — refreshing live QuickFile / Lunch Flow balances…</p>
      ) : null}
    </div>
  );
}
