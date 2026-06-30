import type { ChargeWindowStatus } from "@/lib/schemas";

import { BoltIcon } from "@/components/shared/icons";

type CheapWindowBannerProps = {
  status: ChargeWindowStatus | null;
};

export function CheapWindowBanner({ status }: CheapWindowBannerProps) {
  if (!status) {
    return null;
  }

  // Reassuring, intentional case: importing on purpose during a cheap window.
  if (status.importing_on_cheap_window) {
    return (
      <div
        role="status"
        className="flex items-start gap-3 rounded-2xl border border-sky-300/50 bg-sky-50/90 px-4 py-3 text-sky-900 shadow-sm dark:border-sky-800/50 dark:bg-sky-950/40 dark:text-sky-200"
      >
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-sky-500/15 text-sky-600 dark:text-sky-300">
          <BoltIcon size={16} />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-semibold">Importing on cheap power — this is intentional</p>
          <p className="mt-0.5 text-sm leading-relaxed">{status.message}</p>
        </div>
      </div>
    );
  }

  // Warning case: grid-charge holding the battery but no cheap window matches.
  if (status.source === "unexpected" && status.message) {
    return (
      <div
        role="alert"
        className="flex items-start gap-3 rounded-2xl border border-amber-300/60 bg-amber-50/90 px-4 py-3 text-amber-900 shadow-sm dark:border-amber-800/50 dark:bg-amber-950/40 dark:text-amber-200"
      >
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-amber-500/15 text-amber-600 dark:text-amber-300">
          <BoltIcon size={16} />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-semibold">Unexpected grid import</p>
          <p className="mt-0.5 text-sm leading-relaxed">{status.message}</p>
        </div>
      </div>
    );
  }

  return null;
}
