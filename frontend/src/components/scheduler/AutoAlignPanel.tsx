"use client";

import { useEffect, useState } from "react";

import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { autoScheduleStatusSchema, evStatusSchema, type AutoScheduleStatus } from "@/lib/schemas";

type AutoAlignPanelProps = {
  disabled?: boolean;
};

export function AutoAlignPanel({ disabled = false }: AutoAlignPanelProps) {
  const { user } = useAuth();
  const [status, setStatus] = useState<AutoScheduleStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [evNote, setEvNote] = useState<string | null>(null);
  const [floorInput, setFloorInput] = useState("20");

  useEffect(() => {
    if (!user || user.role !== "admin") return;
    let cancelled = false;
    void (async () => {
      try {
        const data = await apiClient.get("/controls/auto-schedule");
        const parsed = autoScheduleStatusSchema.parse(data);
        if (!cancelled) {
          setStatus(parsed);
          setFloorInput(String(parsed.soc_floor_pct));
          setError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Could not load auto-align status");
        }
      }
      try {
        const ev = evStatusSchema.parse(await apiClient.get("/metrics/ev/status"));
        if (!cancelled && ev.car_charging_likely) {
          setEvNote("EV charging likely — auto-align will skip writes until load drops.");
        } else if (!cancelled) {
          setEvNote(null);
        }
      } catch {
        if (!cancelled) setEvNote(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user]);

  const toggle = async (enabled: boolean) => {
    setSaving(true);
    setError(null);
    try {
      const floor = Number(floorInput);
      const data = await apiClient.post("/controls/auto-schedule", {
        enabled,
        soc_floor_pct: Number.isFinite(floor) ? floor : 20,
      });
      setStatus(autoScheduleStatusSchema.parse(data));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to update auto-align");
    } finally {
      setSaving(false);
    }
  };

  if (!user || user.role !== "admin") {
    return null;
  }

  if (loading) {
    return <p className="text-sm text-[var(--muted)]">Loading auto-align settings…</p>;
  }

  return (
    <section className="solar-card space-y-4" aria-label="Auto-align battery to IOG windows">
      <div>
        <h3 className="solar-section-title">Auto-align to Octopus cheap windows</h3>
        <p className="mt-1 text-sm text-[var(--muted)]">
          When enabled, Rob&apos;s Solar writes your inverter schedule every 15 minutes so the
          battery charges during IOG off-peak and any smart-charge dispatches, then holds your
          floor SOC through the day.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <label className="block text-sm">
          <span className="text-[var(--muted)]">Daytime SOC floor (%)</span>
          <input
            type="number"
            min={0}
            max={100}
            value={floorInput}
            disabled={disabled || saving}
            onChange={(event) => setFloorInput(event.target.value)}
            className="solar-input mt-1 w-24"
          />
        </label>
        <button
          type="button"
          className="solar-btn-primary"
          disabled={disabled || saving || status?.enabled}
          onClick={() => void toggle(true)}
        >
          Enable auto-align
        </button>
        <button
          type="button"
          className="solar-btn-ghost"
          disabled={disabled || saving || !status?.enabled}
          onClick={() => void toggle(false)}
        >
          Disable
        </button>
      </div>

      {evNote ? (
        <p className="rounded-xl border border-sky-300/40 bg-sky-50/80 px-4 py-3 text-sm text-sky-900 dark:bg-sky-950/30 dark:text-sky-200">
          {evNote}
        </p>
      ) : null}

      {status ? (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 text-sm">
          <p>
            Status:{" "}
            <strong>{status.enabled ? "Enabled" : "Disabled"}</strong>
            {status.last_run_message ? ` — ${status.last_run_message}` : ""}
          </p>
          {status.computed_bands.length ? (
            <ul className="mt-2 space-y-1 text-[var(--muted)]">
              {status.computed_bands.map((band) => (
                <li key={band.slot} className="tabular-nums">
                  Band {band.slot}: {band.start} → cap {band.target_soc_pct}% · grid{" "}
                  {band.grid_charge_enabled ? "on" : "off"}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {error ? (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      ) : null}
    </section>
  );
}
