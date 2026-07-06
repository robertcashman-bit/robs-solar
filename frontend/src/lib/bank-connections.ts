import type { BankConnectionItem } from "@/lib/finance-schemas";

/** Plain-English labels for connection status (never show technical errors). */
export function connectionStatusLabel(status: BankConnectionItem["status"]): string {
  switch (status) {
    case "connected":
      return "Connected";
    case "awaiting_login":
      return "Connecting";
    case "needs_reconnection":
      return "Needs Reconnection";
    case "sync_failed":
      return "Sync Failed";
    case "not_connected":
    case "not_configured":
      return "Not Connected";
    case "manual":
      return "Connected";
    default:
      return "Not Connected";
  }
}

export function connectionStatusClass(status: BankConnectionItem["status"]): string {
  switch (status) {
    case "connected":
    case "manual":
      return "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300";
    case "awaiting_login":
      return "bg-sky-500/15 text-sky-800 dark:text-sky-200";
    case "needs_reconnection":
    case "sync_failed":
      return "bg-amber-500/15 text-amber-800 dark:text-amber-200";
    case "not_configured":
      return "bg-amber-500/15 text-amber-800 dark:text-amber-200";
    default:
      return "bg-[var(--surface-sunken)] text-[var(--muted)]";
  }
}

export function formatLastSynced(iso: string | null | undefined): string {
  if (!iso) return "Never";
  try {
    return new Date(iso).toLocaleString("en-GB", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

/** Map backend institution keywords to OB search queries. */
export const CONNECTION_SEARCH: Record<string, string> = {
  lloyds: "Lloyds",
  mbna: "MBNA",
  virgin: "Virgin Money",
};
