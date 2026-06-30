export function formatCountdown(iso: string | null | undefined, nowMs = Date.now()): string {
  if (!iso) {
    return "";
  }
  const target = new Date(iso).getTime();
  if (Number.isNaN(target)) {
    return "";
  }
  const diffMs = Math.max(0, target - nowMs);
  const totalMinutes = Math.ceil(diffMs / 60_000);
  if (totalMinutes < 60) {
    return `${totalMinutes}m`;
  }
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
}

export function formatLocalTime(iso: string | null | undefined): string {
  if (!iso) {
    return "";
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function formatWindowRange(windows: { start: string; end: string }[]): string {
  if (windows.length === 0) {
    return "—";
  }
  return windows.map((w) => `${w.start}–${w.end}`).join(", ");
}
