"use client";

import { useState } from "react";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { RefreshIcon } from "@/components/shared/icons";

type RestoreConfigButtonProps = {
  readOnlyMode?: boolean;
  onRestore: () => Promise<void>;
};

export function RestoreConfigButton({
  readOnlyMode = true,
  onRestore,
}: RestoreConfigButtonProps) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleRestore = async () => {
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      await onRestore();
      setSuccess("Last known good configuration restored");
      setConfirmOpen(false);
    } catch (restoreError) {
      setError(restoreError instanceof Error ? restoreError.message : "Restore failed");
      setConfirmOpen(false);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="solar-card">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300">
          <RefreshIcon size={20} />
        </div>
        <div>
          <h2 className="text-lg font-semibold">Restore configuration</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Re-apply the last known good export limit and operating mode from the adapter snapshot.
          </p>
        </div>
      </div>

      {readOnlyMode ? (
        <p role="status" className="mt-4 rounded-xl border border-amber-300/40 bg-amber-50/80 px-3 py-2 text-sm text-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
          Restore is disabled while the backend is in read-only mode.
        </p>
      ) : null}

      {error ? (
        <p role="alert" className="mt-4 text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      ) : null}
      {success ? (
        <p role="status" className="mt-4 text-sm text-emerald-700 dark:text-emerald-400">
          {success}
        </p>
      ) : null}

      <button
        type="button"
        disabled={readOnlyMode || submitting}
        onClick={() => setConfirmOpen(true)}
        className="solar-btn-ghost mt-4 border-amber-500/40 text-amber-800 dark:text-amber-300 disabled:opacity-40"
      >
        Restore last known good
      </button>

      <ConfirmDialog
        open={confirmOpen}
        title="Confirm restore"
        description="Restore the last known good configuration? This will attempt to re-apply saved settings via the backend."
        confirmLabel="Restore"
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => void handleRestore()}
      />
    </section>
  );
}
