import type { BankConnectionItem } from "@/lib/finance-schemas";
import { ApiError } from "@/lib/api-client";

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

export const ENABLE_BANKING_CP_URL = "https://enablebanking.com/cp/applications";

/** Turn Open Banking connect API errors into plain-English guidance. */
export function mapOpenBankingConnectError(err: unknown): string {
  const activationMessage =
    "Your Open Banking app is not active yet. An admin must sign in at Enable Banking Control Panel and complete activation by linking accounts, then return here and press Connect again.";

  if (err instanceof ApiError) {
    if (
      err.code === "further_bank_authorisation_required" ||
      /not active|activate/i.test(err.message)
    ) {
      return activationMessage;
    }
    return err.message;
  }

  if (err instanceof Error) {
    if (/not active|activate/i.test(err.message)) {
      return activationMessage;
    }
    return err.message;
  }

  return "Could not start bank connection. Try again or check Open Banking Settings.";
}
