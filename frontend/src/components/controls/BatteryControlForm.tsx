"use client";

import { useState } from "react";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";

type BatteryControlFormProps = {
  readOnlyMode: boolean;
  disabled?: boolean;
  onSubmit: (payload: {
    charge_current_a?: number;
    discharge_current_a?: number;
    grid_charge_current_a?: number;
  }) => Promise<void>;
  onForce: (action: "charge" | "discharge" | "stop") => Promise<void>;
};

export function BatteryControlForm({
  readOnlyMode,
  disabled,
  onSubmit,
  onForce,
}: BatteryControlFormProps) {
  const [charge, setCharge] = useState(50);
  const [discharge, setDischarge] = useState(50);
  const [gridCharge, setGridCharge] = useState(20);
  const [confirmForce, setConfirmForce] = useState<"charge" | "discharge" | "stop" | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const blocked = readOnlyMode || disabled;

  const showToast = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 4000);
  };

  return (
    <section className="solar-card space-y-4">
      <div>
        <h3 className="solar-section-title">Battery limits</h3>
        <p className="text-sm text-[var(--muted)]">
          Charge ≤190 A, discharge ≤190 A, grid charge ≤50 A (clamped server-side).
        </p>
      </div>
      {toast ? (
        <p className="rounded-lg bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-300">
          {toast}
        </p>
      ) : null}
      <label className="block text-sm">
        Max charge current (A)
        <input
          type="range"
          min={0}
          max={190}
          value={charge}
          disabled={blocked}
          onChange={(e) => setCharge(Number(e.target.value))}
          className="mt-1 w-full"
        />
        <span className="tabular-nums">{charge} A</span>
      </label>
      <label className="block text-sm">
        Max discharge current (A)
        <input
          type="range"
          min={0}
          max={190}
          value={discharge}
          disabled={blocked}
          onChange={(e) => setDischarge(Number(e.target.value))}
          className="mt-1 w-full"
        />
        <span className="tabular-nums">{discharge} A</span>
      </label>
      <label className="block text-sm">
        Grid charge current (A)
        <input
          type="range"
          min={0}
          max={50}
          value={gridCharge}
          disabled={blocked}
          onChange={(e) => setGridCharge(Number(e.target.value))}
          className="mt-1 w-full"
        />
        <span className="tabular-nums">{gridCharge} A</span>
      </label>
      <button
        type="button"
        className="solar-btn-primary"
        disabled={blocked}
        onClick={() =>
          void onSubmit({
            charge_current_a: charge,
            discharge_current_a: discharge,
            grid_charge_current_a: gridCharge,
          }).then(() => showToast("Battery limits applied"))
        }
      >
        Apply battery limits
      </button>
      <div className="flex flex-wrap gap-2 border-t border-[var(--border)] pt-4">
        {(["charge", "discharge", "stop"] as const).map((action) => (
          <button
            key={action}
            type="button"
            className="solar-btn-ghost capitalize"
            disabled={blocked}
            onClick={() => setConfirmForce(action)}
          >
            Force {action}
          </button>
        ))}
      </div>
      <ConfirmDialog
        open={confirmForce != null}
        title={confirmForce ? `Force ${confirmForce}?` : "Confirm"}
        description="This writes directly to the inverter. Confirm only if live writes are enabled."
        confirmLabel="Confirm"
        onCancel={() => setConfirmForce(null)}
        onConfirm={() => {
          if (!confirmForce) return;
          const action = confirmForce;
          setConfirmForce(null);
          void onForce(action).then(() => showToast(`Force ${action} sent`));
        }}
      />
    </section>
  );
}
