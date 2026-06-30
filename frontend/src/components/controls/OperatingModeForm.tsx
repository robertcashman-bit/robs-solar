"use client";

import { useMemo, useState } from "react";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { GaugeIcon } from "@/components/shared/icons";
import { operatingModeSchema } from "@/lib/schemas";

const MODES = [
  { value: "self_use", label: "Self use" },
  { value: "backup", label: "Backup" },
  { value: "feed_in", label: "Feed in" },
  { value: "off_grid", label: "Off grid" },
] as const;

type OperatingModeFormProps = {
  readOnlyMode?: boolean;
  onSubmit: (mode: string) => Promise<void>;
};

export function OperatingModeForm({
  readOnlyMode = true,
  onSubmit,
}: OperatingModeFormProps) {
  const [mode, setMode] = useState("self_use");
  const [error, setError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);

  const parsed = useMemo(() => operatingModeSchema.safeParse({ mode }), [mode]);
  const formDisabled = readOnlyMode;

  const handleSubmit = async () => {
    const result = operatingModeSchema.safeParse({ mode });
    if (!result.success) {
      setError(result.error.issues[0]?.message ?? "Invalid operating mode");
      return;
    }
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      await onSubmit(result.data.mode);
      setSuccess(`Operating mode set to ${result.data.mode.replaceAll("_", " ")}`);
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
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300">
          <GaugeIcon size={20} />
        </div>
        <div>
          <h2 className="text-lg font-semibold">Operating mode</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">Change the inverter operating mode.</p>
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
          const result = operatingModeSchema.safeParse({ mode });
          if (!result.success) {
            setError(result.error.issues[0]?.message ?? "Invalid operating mode");
            return;
          }
          setConfirmOpen(true);
        }}
      >
        <label className="block text-sm font-medium">
          Mode
          <select
            value={mode}
            disabled={formDisabled}
            onChange={(event) => setMode(event.target.value)}
            className="solar-input"
          >
            {MODES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
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
        title="Confirm operating mode change"
        description={`Apply operating mode "${parsed.success ? parsed.data.mode.replaceAll("_", " ") : mode}" via the backend bridge?`}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => void handleSubmit()}
      />
    </section>
  );
}
