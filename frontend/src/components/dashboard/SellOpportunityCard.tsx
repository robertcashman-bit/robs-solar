import { useState } from "react";

import type { SellOpportunity } from "@/lib/schemas";
import { apiClient, ApiError } from "@/lib/api-client";
import { controlWriteResultSchema } from "@/lib/schemas";

import { ArrowUpIcon } from "@/components/shared/icons";

type SellOpportunityCardProps = {
  opportunity: SellOpportunity | null;
  canControl: boolean;
  onRefresh?: () => void | Promise<void>;
};

export function SellOpportunityCard({
  opportunity,
  canControl,
  onRefresh,
}: SellOpportunityCardProps) {
  const [busy, setBusy] = useState<"sell" | "stop" | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [errored, setErrored] = useState(false);

  if (!opportunity || !opportunity.configured) {
    return null;
  }

  const applyMode = async (mode: "feed_in" | "self_use", kind: "sell" | "stop") => {
    setBusy(kind);
    setFeedback(null);
    setErrored(false);
    try {
      const result = controlWriteResultSchema.parse(
        await apiClient.post("/controls/operating-mode", { mode }),
      );
      if (!result.success) {
        throw new ApiError(result.message ?? "Inverter rejected the change", 502);
      }
      setFeedback(
        mode === "feed_in"
          ? "Selling to grid — inverter switched to Feed-in mode."
          : "Stopped selling — inverter back to self-use.",
      );
      if (onRefresh) {
        await onRefresh();
      }
    } catch (err) {
      setErrored(true);
      setFeedback(err instanceof Error ? err.message : "Could not change inverter mode.");
    } finally {
      setBusy(null);
    }
  };

  const worth = opportunity.worth_selling;

  return (
    <section
      aria-label="Sell to grid"
      className={`flex flex-col gap-3 rounded-2xl border px-4 py-4 shadow-sm sm:flex-row sm:items-center sm:justify-between ${
        worth
          ? "border-emerald-300/60 bg-emerald-50/90 text-emerald-950 dark:border-emerald-800/50 dark:bg-emerald-950/40 dark:text-emerald-100"
          : "border-[var(--border)] bg-[var(--card)] text-[var(--foreground)]"
      }`}
    >
      <div className="flex items-start gap-3">
        <span
          className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
            worth
              ? "bg-emerald-500/20 text-emerald-600 dark:text-emerald-300"
              : "bg-zinc-500/10 text-[var(--muted)]"
          }`}
        >
          <ArrowUpIcon size={18} />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-semibold">{opportunity.headline || "Sell to grid"}</p>
          <p className="mt-0.5 text-sm leading-relaxed text-[var(--muted)]">
            {opportunity.message}
          </p>
          {worth ? (
            <p className="mt-1 text-xs font-medium text-emerald-700 dark:text-emerald-300">
              {opportunity.export_rate_pence?.toFixed(1)}p/kWh · ~
              {opportunity.sellable_kwh.toFixed(1)} kWh · ≈£
              {opportunity.estimated_value_gbp.toFixed(2)}
            </p>
          ) : null}
          {feedback ? (
            <p
              className={`mt-2 text-xs font-medium ${
                errored ? "text-rose-600 dark:text-rose-400" : "text-emerald-700 dark:text-emerald-300"
              }`}
            >
              {feedback}
            </p>
          ) : null}
        </div>
      </div>

      {canControl ? (
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={() => applyMode("feed_in", "sell")}
            disabled={busy !== null || !worth}
            className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy === "sell" ? "Switching…" : "Sell now"}
          </button>
          <button
            type="button"
            onClick={() => applyMode("self_use", "stop")}
            disabled={busy !== null}
            className="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-semibold text-[var(--foreground)] transition hover:bg-black/5 disabled:cursor-not-allowed disabled:opacity-50 dark:hover:bg-white/5"
          >
            {busy === "stop" ? "Switching…" : "Stop selling"}
          </button>
        </div>
      ) : null}
    </section>
  );
}
