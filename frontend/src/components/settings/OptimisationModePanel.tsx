"use client";

import { useState } from "react";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { apiClient } from "@/lib/api-client";
import { optimisationModeSchema, type OptimisationModeSettings } from "@/lib/schemas";

type OptimisationModePanelProps = {
  initial: OptimisationModeSettings;
  readOnly?: boolean;
};

export function OptimisationModePanel({ initial, readOnly = false }: OptimisationModePanelProps) {
  const [settings, setSettings] = useState(initial);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const save = async () => {
    setError(null);
    setSuccess(null);
    try {
      const parsed = optimisationModeSchema.parse(settings);
      const data = await apiClient.put("/optimisation/mode", parsed);
      setSettings(optimisationModeSchema.parse(data));
      setSuccess("Optimisation mode updated");
      setConfirmOpen(false);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Update failed");
      setConfirmOpen(false);
    }
  };

  return (
    <section className="solar-card">
      <h2 className="text-lg font-semibold">Optimisation mode</h2>
      <p className="mt-1 text-sm text-[var(--muted)]">
        Default is read-only. Auto-optimise only applies safe categories you enable below.
      </p>
      <div className="mt-4 space-y-3">
        <label className="block text-sm font-medium">
          Mode
          <select
            disabled={readOnly}
            value={settings.mode}
            onChange={(e) =>
              setSettings((s) => ({
                ...s,
                mode: e.target.value as OptimisationModeSettings["mode"],
              }))
            }
            className="solar-input"
          >
            <option value="read_only">Read-only (recommend only)</option>
            <option value="confirm">Confirm before change</option>
            <option value="auto">Auto-optimise (allowed categories)</option>
          </select>
        </label>
        {(
          [
            ["allow_auto_charge_window_changes", "Auto charge window changes"],
            ["allow_auto_discharge_window_changes", "Auto discharge window changes"],
            ["allow_auto_reserve_changes", "Auto reserve SOC changes"],
            ["allow_auto_grid_charge_changes", "Auto grid charge changes"],
          ] as const
        ).map(([key, label]) => (
          <label key={key} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              disabled={readOnly}
              checked={settings[key]}
              onChange={(e) => setSettings((s) => ({ ...s, [key]: e.target.checked }))}
            />
            {label}
          </label>
        ))}
      </div>
      {error ? <p className="mt-2 text-sm text-red-600">{error}</p> : null}
      {success ? <p className="mt-2 text-sm text-emerald-600">{success}</p> : null}
      {!readOnly ? (
        <button type="button" className="solar-btn-primary mt-4" onClick={() => setConfirmOpen(true)}>
          Save optimisation mode
        </button>
      ) : null}
      <ConfirmDialog
        open={confirmOpen}
        title="Confirm optimisation mode"
        description="Update how the app applies optimisation recommendations?"
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => void save()}
      />
    </section>
  );
}
