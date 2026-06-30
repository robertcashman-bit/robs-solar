"use client";

import type { InverterSettings } from "@/lib/schemas";

type LiveInverterSettingsProps = {
  settings: InverterSettings | null;
  loading?: boolean;
  error?: string | null;
};

export function LiveInverterSettings({
  settings,
  loading = false,
  error = null,
}: LiveInverterSettingsProps) {
  if (loading) {
    return (
      <section className="solar-card" aria-label="Live inverter TOU settings loading">
        <p className="text-sm text-[var(--muted)]">Loading inverter time-of-use settings…</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="solar-card" aria-label="Live inverter TOU settings error">
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      </section>
    );
  }

  if (!settings) {
    return null;
  }

  return (
    <section className="solar-card space-y-4" aria-label="Live inverter TOU settings">
      <div>
        <h3 className="solar-section-title">Live inverter schedule</h3>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Read from Sunsynk for {settings.plant_name || "your plant"} (SN {settings.inverter_sn}).
          Mode: {settings.sys_work_mode_label}.
        </p>
      </div>

      {!settings.write_allowed && settings.write_denied_reason ? (
        <div className="space-y-2">
          <p
            role="status"
            className="rounded-xl border border-amber-300/40 bg-amber-50/80 px-3 py-2 text-sm text-amber-900 dark:bg-amber-950/30 dark:text-amber-200"
          >
            {settings.write_denied_reason}
          </p>
          <p className="text-sm text-[var(--muted)]">
            Changes made in Simple Solar or Sunsynk Connect may not reach the inverter while access
            is view-only. The table below is what your inverter is actually running right now.
          </p>
        </div>
      ) : null}

      {settings.diagnosis ? (
        <p
          role="status"
          className="rounded-xl border border-sky-300/40 bg-sky-50/80 px-3 py-2 text-sm text-sky-900 dark:bg-sky-950/30 dark:text-sky-200"
        >
          {settings.active_band
            ? `Now ${settings.active_band.start}–${settings.active_band.end}: `
            : "Now: "}
          {settings.diagnosis}
        </p>
      ) : null}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[32rem] text-left text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] text-[var(--muted)]">
              <th className="py-2 pr-3 font-medium">Band</th>
              <th className="py-2 pr-3 font-medium">Time</th>
              <th className="py-2 pr-3 font-medium">Cap SOC</th>
              <th className="py-2 pr-3 font-medium">Grid charge</th>
              <th className="py-2 font-medium">Power</th>
            </tr>
          </thead>
          <tbody>
            {settings.bands.map((band) => {
              const active = band.slot === settings.active_band_slot;
              return (
                <tr
                  key={band.slot}
                  className={
                    active
                      ? "border-b border-[var(--border)] bg-amber-500/10 font-medium"
                      : "border-b border-[var(--border)]"
                  }
                >
                  <td className="py-2 pr-3">{band.slot}</td>
                  <td className="py-2 pr-3">
                    {band.start}–{band.end}
                    {active ? " · now" : ""}
                  </td>
                  <td className="py-2 pr-3">
                    {band.target_soc_pct != null ? `${band.target_soc_pct}%` : "—"}
                  </td>
                  <td className="py-2 pr-3">{band.grid_charge_enabled ? "On" : "Off"}</td>
                  <td className="py-2">{band.power_w != null ? `${band.power_w} W` : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
