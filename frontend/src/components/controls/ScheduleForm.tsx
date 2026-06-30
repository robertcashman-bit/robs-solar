"use client";

import { useState } from "react";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { BatteryIcon } from "@/components/shared/icons";
import { scheduleSchema } from "@/lib/schemas";

type ScheduleFormProps = {
  readOnlyMode?: boolean;
  onSubmit: (windows: Array<{ start: string; end: string; action: string; power_w?: number }>) => Promise<void>;
};

export function ScheduleForm({ readOnlyMode = true, onSubmit }: ScheduleFormProps) {
  const [start, setStart] = useState("00:00");
  const [end, setEnd] = useState("06:00");
  const [action, setAction] = useState("charge");
  const [powerW, setPowerW] = useState("2000");
  const [error, setError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);

  const formDisabled = readOnlyMode;

  const buildPayload = () => ({
    windows: [
      {
        start,
        end,
        action,
        power_w: action === "idle" ? undefined : Number(powerW),
      },
    ],
  });

  const handleSubmit = async () => {
    const result = scheduleSchema.safeParse(buildPayload());
    if (!result.success) {
      setError(result.error.issues[0]?.message ?? "Invalid schedule");
      return;
    }
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      await onSubmit(result.data.windows);
      setSuccess("Schedule updated");
      setConfirmOpen(false);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Write failed");
      setConfirmOpen(false);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="solar-card">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
          <BatteryIcon size={20} />
        </div>
        <div>
          <h2 className="text-lg font-semibold">Battery schedule</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Configure a charge, discharge, or idle window.
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
          const result = scheduleSchema.safeParse(buildPayload());
          if (!result.success) {
            setError(result.error.issues[0]?.message ?? "Invalid schedule");
            return;
          }
          setConfirmOpen(true);
        }}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm font-medium">
            Start time
            <input
              type="time"
              value={start}
              disabled={formDisabled}
              onChange={(event) => setStart(event.target.value)}
              className="solar-input"
            />
          </label>
          <label className="block text-sm font-medium">
            End time
            <input
              type="time"
              value={end}
              disabled={formDisabled}
              onChange={(event) => setEnd(event.target.value)}
              className="solar-input"
            />
          </label>
        </div>

        <label className="block text-sm font-medium">
          Action
          <select
            value={action}
            disabled={formDisabled}
            onChange={(event) => setAction(event.target.value)}
            className="solar-input"
          >
            <option value="charge">Charge</option>
            <option value="discharge">Discharge</option>
            <option value="idle">Idle</option>
          </select>
        </label>

        {action !== "idle" ? (
          <label className="block text-sm font-medium">
            Power (W)
            <input
              type="number"
              step="100"
              min="0"
              max="8000"
              value={powerW}
              disabled={formDisabled}
              onChange={(event) => setPowerW(event.target.value)}
              className="solar-input"
            />
          </label>
        ) : null}

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
        title="Confirm schedule change"
        description={`Apply schedule window ${start}–${end} (${action}) via the backend bridge?`}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => void handleSubmit()}
      />
    </section>
  );
}
