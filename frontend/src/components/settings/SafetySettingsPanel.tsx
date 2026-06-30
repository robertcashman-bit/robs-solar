"use client";

import { useState } from "react";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import type { SafetySettings } from "@/lib/schemas";

type SafetySettingsPanelProps = {
  initial: SafetySettings;
  onSubmit: (update: { read_only?: boolean; enable_live_writes?: boolean }) => Promise<void>;
};

export function SafetySettingsPanel({ initial, onSubmit }: SafetySettingsPanelProps) {
  const [readOnly, setReadOnly] = useState(initial.read_only);
  const [liveWrites, setLiveWrites] = useState(initial.enable_live_writes);
  const [confirmLive, setConfirmLive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const save = async (payload: { read_only?: boolean; enable_live_writes?: boolean }) => {
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      await onSubmit(payload);
      setSuccess("Safety settings updated");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="solar-card space-y-4">
      <div>
        <h3 className="solar-section-title">Runtime safety toggles</h3>
        <p className="text-sm text-[var(--muted)]">
          Override env defaults without restarting the backend.
          {initial.runtime_overrides ? " Runtime overrides active." : " Using env defaults."}
        </p>
      </div>
      <label className="flex items-center justify-between gap-4 rounded-xl border border-[var(--border)] p-4">
        <div>
          <p className="font-medium">Read-only mode</p>
          <p className="text-xs text-[var(--muted)]">Blocks all control writes at the API layer.</p>
        </div>
        <input
          type="checkbox"
          checked={readOnly}
          onChange={(e) => {
            const next = e.target.checked;
            setReadOnly(next);
            void save({ read_only: next, enable_live_writes: liveWrites });
          }}
        />
      </label>
      <label className="flex items-center justify-between gap-4 rounded-xl border border-[var(--border)] p-4">
        <div>
          <p className="font-medium">Enable live writes</p>
          <p className="text-xs text-[var(--muted)]">Allows non-simulator adapters to write to the inverter.</p>
        </div>
        <input
          type="checkbox"
          checked={liveWrites}
          onChange={(e) => {
            if (e.target.checked) {
              setConfirmLive(true);
            } else {
              setLiveWrites(false);
              void save({ read_only: readOnly, enable_live_writes: false });
            }
          }}
        />
      </label>
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
      {success ? <p className="text-sm text-emerald-600">{success}</p> : null}
      <ConfirmDialog
        open={confirmLive}
        title="Enable live inverter writes?"
        description="This allows the backend to send real commands to your Sunsynk inverter. Only enable when you intend to make live changes."
        confirmLabel={submitting ? "Enabling…" : "Enable live writes"}
        onConfirm={() => {
          setLiveWrites(true);
          setConfirmLive(false);
          void save({ read_only: readOnly, enable_live_writes: true });
        }}
        onCancel={() => setConfirmLive(false)}
      />
    </section>
  );
}
