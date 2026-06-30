"use client";

import { useMemo, useState } from "react";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { ArrowUpIcon } from "@/components/shared/icons";
import { exportLimitSchema } from "@/lib/schemas";

type ExportLimitFormProps = {
  disabled?: boolean;
  readOnlyMode?: boolean;
  onSubmit: (limitW: number) => Promise<void>;
};

export function ExportLimitForm({
  disabled = false,
  readOnlyMode = true,
  onSubmit,
}: ExportLimitFormProps) {
  const [limitW, setLimitW] = useState("3000");
  const [error, setError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);

  const parsed = useMemo(() => {
    const numeric = Number(limitW);
    return exportLimitSchema.safeParse({ limit_w: numeric });
  }, [limitW]);

  const validateCurrent = () => exportLimitSchema.safeParse({ limit_w: Number(limitW) });

  const handleSubmit = async () => {
    const result = validateCurrent();
    if (!result.success) {
      setError(result.error.issues[0]?.message ?? "Invalid export limit");
      return;
    }
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      await onSubmit(result.data.limit_w);
      setSuccess(`Export limit set to ${result.data.limit_w} W`);
      setConfirmOpen(false);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Write failed");
      setConfirmOpen(false);
    } finally {
      setSubmitting(false);
    }
  };

  const formDisabled = disabled || readOnlyMode;

  return (
    <section className="solar-card">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300">
          <ArrowUpIcon size={20} />
        </div>
        <div>
          <h2 className="text-lg font-semibold">Export limit</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Set the maximum export power in watts. Must be a multiple of 100W.
          </p>
        </div>
      </div>

      {readOnlyMode ? (
        <p role="status" className="mt-4 rounded-xl border border-amber-300/40 bg-amber-50/80 px-3 py-2 text-sm text-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
          Controls are disabled while the backend is in read-only mode.
        </p>
      ) : null}

      <form
        className="mt-4 space-y-4"
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          if (formDisabled) {
            return;
          }
          const result = validateCurrent();
          if (!result.success) {
            setError(result.error.issues[0]?.message ?? "Invalid export limit");
            return;
          }
          setConfirmOpen(true);
        }}
      >
        <label className="block text-sm font-medium">
          Export limit (W)
          <input
            type="number"
            step="100"
            min="0"
            max="8000"
            value={limitW}
            disabled={formDisabled}
            onChange={(event) => setLimitW(event.target.value)}
            className="solar-input"
          />
        </label>

        {error ? (
          <p role="alert" className="text-sm text-red-600 dark:text-red-400">
            {error}
          </p>
        ) : null}
        {success ? (
          <p role="status" className="text-sm text-emerald-700 dark:text-emerald-400">
            {success}
          </p>
        ) : null}

        <button type="submit" disabled={formDisabled || submitting} className="solar-btn-primary">
          Review change
        </button>
      </form>

      <ConfirmDialog
        open={confirmOpen}
        title="Confirm export limit change"
        description={`Apply export limit of ${parsed.success ? parsed.data.limit_w : limitW} W to the inverter via the backend bridge?`}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => void handleSubmit()}
      />
    </section>
  );
}
