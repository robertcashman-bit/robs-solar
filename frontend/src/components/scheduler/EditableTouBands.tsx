"use client";

import { useState } from "react";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { GaugeIcon } from "@/components/shared/icons";
import type { InverterSettings, TouBandWrite } from "@/lib/schemas";
import { touBandsRequestSchema } from "@/lib/schemas";

type EditableTouBandsProps = {
  settings: InverterSettings;
  onSubmit: (bands: TouBandWrite[]) => Promise<{
    verified?: boolean;
    verification_pending?: boolean;
    verification_message?: string;
  } | void>;
  disabled?: boolean;
};

type DraftBand = {
  slot: number;
  start: string;
  target_soc_pct: string;
  grid_charge_enabled: boolean;
  power_w: string;
};

function toDraft(settings: InverterSettings): DraftBand[] {
  return settings.bands.map((band) => ({
    slot: band.slot,
    start: band.start,
    target_soc_pct: band.target_soc_pct != null ? String(band.target_soc_pct) : "",
    grid_charge_enabled: band.grid_charge_enabled,
    power_w: band.power_w != null ? String(band.power_w) : "",
  }));
}

export function EditableTouBands({ settings, onSubmit, disabled = false }: EditableTouBandsProps) {
  const [draft, setDraft] = useState<DraftBand[]>(() => toDraft(settings));
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const update = (slot: number, patch: Partial<DraftBand>) => {
    setDraft((rows) => rows.map((row) => (row.slot === slot ? { ...row, ...patch } : row)));
    setSuccess(null);
  };

  const buildPayload = (): TouBandWrite[] =>
    draft.map((row) => ({
      slot: row.slot,
      start: row.start,
      target_soc_pct: row.target_soc_pct === "" ? undefined : Number(row.target_soc_pct),
      grid_charge_enabled: row.grid_charge_enabled,
      power_w: row.power_w === "" ? undefined : Number(row.power_w),
    }));

  const handleSubmit = async () => {
    const parsed = touBandsRequestSchema.safeParse({ bands: buildPayload() });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Invalid schedule");
      setConfirmOpen(false);
      return;
    }
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await onSubmit(parsed.data.bands);
      if (result?.verified) {
        setSuccess(result.verification_message || "Schedule confirmed on inverter.");
      } else if (result?.verification_pending) {
        setSuccess(
          result.verification_message ||
            "Write sent — Sunsynk can take up to a minute to report matching values.",
        );
      } else {
        setSuccess(
          "Schedule written to the inverter. Sunsynk can take up to a minute to report the new values back.",
        );
      }
      setConfirmOpen(false);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Write failed");
      setConfirmOpen(false);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="solar-card space-y-4" aria-label="Edit inverter schedule">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">
          <GaugeIcon size={20} />
        </div>
        <div>
          <h3 className="solar-section-title">Edit schedule</h3>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Change each band&apos;s start time, target SOC cap, grid charge, and power, then write
            it straight to the inverter (SN {settings.inverter_sn}).
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[40rem] text-left text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] text-[var(--muted)]">
              <th className="py-2 pr-3 font-medium">Band</th>
              <th className="py-2 pr-3 font-medium">Start</th>
              <th className="py-2 pr-3 font-medium">Cap SOC %</th>
              <th className="py-2 pr-3 font-medium">Grid charge</th>
              <th className="py-2 font-medium">Power (W)</th>
            </tr>
          </thead>
          <tbody>
            {draft.map((row) => (
              <tr key={row.slot} className="border-b border-[var(--border)]">
                <td className="py-2 pr-3 tabular-nums">{row.slot}</td>
                <td className="py-2 pr-3">
                  <input
                    type="time"
                    value={row.start}
                    disabled={disabled}
                    onChange={(event) => update(row.slot, { start: event.target.value })}
                    className="solar-input w-32"
                    aria-label={`Band ${row.slot} start time`}
                  />
                </td>
                <td className="py-2 pr-3">
                  <input
                    type="number"
                    min={0}
                    max={100}
                    step={1}
                    value={row.target_soc_pct}
                    disabled={disabled}
                    onChange={(event) => update(row.slot, { target_soc_pct: event.target.value })}
                    className="solar-input w-24"
                    aria-label={`Band ${row.slot} target SOC`}
                  />
                </td>
                <td className="py-2 pr-3">
                  <label className="inline-flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={row.grid_charge_enabled}
                      disabled={disabled}
                      onChange={(event) =>
                        update(row.slot, { grid_charge_enabled: event.target.checked })
                      }
                      aria-label={`Band ${row.slot} grid charge`}
                    />
                    <span>{row.grid_charge_enabled ? "On" : "Off"}</span>
                  </label>
                </td>
                <td className="py-2">
                  <input
                    type="number"
                    min={0}
                    max={10000}
                    step={100}
                    value={row.power_w}
                    disabled={disabled}
                    onChange={(event) => update(row.slot, { power_w: event.target.value })}
                    className="solar-input w-28"
                    aria-label={`Band ${row.slot} power`}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

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

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="solar-btn-primary"
          disabled={disabled || submitting}
          onClick={() => {
            const parsed = touBandsRequestSchema.safeParse({ bands: buildPayload() });
            if (!parsed.success) {
              setError(parsed.error.issues[0]?.message ?? "Invalid schedule");
              return;
            }
            setError(null);
            setConfirmOpen(true);
          }}
        >
          Review &amp; write to inverter
        </button>
        <button
          type="button"
          className="solar-btn-ghost"
          disabled={disabled || submitting}
          onClick={() => {
            setDraft(toDraft(settings));
            setError(null);
            setSuccess(null);
          }}
        >
          Reset
        </button>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title="Write schedule to inverter?"
        description="This sends all six time-of-use bands to your Sunsynk inverter immediately. The change is audited and a snapshot is saved."
        confirmLabel="Write to inverter"
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => void handleSubmit()}
      />
    </section>
  );
}
