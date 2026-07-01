"use client";

import { useState } from "react";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { tariffSettingsSchema, type TariffSettings } from "@/lib/schemas";

type TariffSettingsFormProps = {
  initial: TariffSettings;
  readOnly?: boolean;
  onSubmit: (tariff: TariffSettings) => Promise<void>;
};

function numField(value: number | undefined | null, fallback = ""): string {
  return value === undefined || value === null ? fallback : String(value);
}

export function TariffSettingsForm({
  initial,
  readOnly = false,
  onSubmit,
}: TariffSettingsFormProps) {
  const [importRate, setImportRate] = useState(String(initial.import_rate));
  const [exportRate, setExportRate] = useState(String(initial.export_rate));
  const [currency, setCurrency] = useState(initial.currency);
  const [nightImportRate, setNightImportRate] = useState(
    numField(initial.night_import_rate),
  );
  const [standingCharge, setStandingCharge] = useState(
    numField(initial.standing_charge_gbp, "0"),
  );
  const [includeStandingCharge, setIncludeStandingCharge] = useState(
    initial.include_standing_charge ?? false,
  );
  const [offPeakStart, setOffPeakStart] = useState(initial.off_peak_start ?? "23:30");
  const [offPeakEnd, setOffPeakEnd] = useState(initial.off_peak_end ?? "05:30");
  const [peakStart, setPeakStart] = useState(initial.peak_start ?? "07:00");
  const [peakEnd, setPeakEnd] = useState(initial.peak_end ?? "23:00");
  const [batteryCapacity, setBatteryCapacity] = useState(
    numField(initial.battery_capacity_kwh, "16.1"),
  );
  const [batteryMinReserve, setBatteryMinReserve] = useState(
    numField(initial.battery_minimum_reserve_pct, "20"),
  );
  const [maximumCharge, setMaximumCharge] = useState(
    numField(initial.maximum_charge_pct, "100"),
  );
  const [warningImportThreshold, setWarningImportThreshold] = useState(
    numField(initial.warning_import_threshold_w, "300"),
  );
  const [warningBatterySoc, setWarningBatterySoc] = useState(
    numField(initial.warning_battery_soc_threshold_pct, "90"),
  );
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const buildPayload = (): TariffSettings | null => {
    const result = tariffSettingsSchema.safeParse({
      import_rate: Number(importRate),
      export_rate: Number(exportRate),
      currency: currency.toUpperCase(),
      night_import_rate: nightImportRate.trim() ? Number(nightImportRate) : null,
      standing_charge_gbp: Number(standingCharge),
      include_standing_charge: includeStandingCharge,
      off_peak_start: offPeakStart,
      off_peak_end: offPeakEnd,
      peak_start: peakStart,
      peak_end: peakEnd,
      battery_capacity_kwh: Number(batteryCapacity),
      battery_minimum_reserve_pct: Number(batteryMinReserve),
      maximum_charge_pct: Number(maximumCharge),
      warning_import_threshold_w: Number(warningImportThreshold),
      warning_battery_soc_threshold_pct: Number(warningBatterySoc),
    });
    if (!result.success) {
      setError(result.error.issues[0]?.message ?? "Invalid tariff");
      return null;
    }
    return result.data;
  };

  const handleSubmit = async () => {
    const payload = buildPayload();
    if (!payload) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      await onSubmit(payload);
      setSuccess("Tariff updated");
      setConfirmOpen(false);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Update failed");
      setConfirmOpen(false);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="solar-card">
      <h2 className="text-lg font-semibold">Electricity tariff</h2>
      <p className="mt-1 text-sm text-[var(--muted)]">
        Rates, standing charge, cheap/peak windows, and battery assumptions used for savings
        calculations and warnings.
      </p>

      <form
        className="mt-4 space-y-6"
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          if (readOnly) {
            return;
          }
          const payload = buildPayload();
          if (!payload) {
            return;
          }
          setConfirmOpen(true);
        }}
      >
        <div className="space-y-4">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
            Rates
          </h3>
          <label className="block text-sm font-medium">
            Import rate (per kWh)
            <input
              type="number"
              step="0.01"
              min="0"
              max="10"
              value={importRate}
              disabled={readOnly}
              onChange={(event) => setImportRate(event.target.value)}
              className="solar-input"
            />
          </label>
          <label className="block text-sm font-medium">
            Night / off-peak import rate (per kWh)
            <input
              type="number"
              step="0.01"
              min="0"
              max="10"
              value={nightImportRate}
              disabled={readOnly}
              onChange={(event) => setNightImportRate(event.target.value)}
              className="solar-input"
              placeholder="Same as day rate if blank"
            />
          </label>
          <label className="block text-sm font-medium">
            Export rate (per kWh)
            <input
              type="number"
              step="0.01"
              min="0"
              max="10"
              value={exportRate}
              disabled={readOnly}
              onChange={(event) => setExportRate(event.target.value)}
              className="solar-input"
            />
          </label>
          <label className="block text-sm font-medium">
            Currency
            <input
              type="text"
              maxLength={3}
              value={currency}
              disabled={readOnly}
              onChange={(event) => setCurrency(event.target.value.toUpperCase())}
              className="solar-input"
            />
          </label>
        </div>

        <div className="space-y-4">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
            Standing charge
          </h3>
          <label className="block text-sm font-medium">
            Daily standing charge (GBP)
            <input
              type="number"
              step="0.01"
              min="0"
              max="10"
              value={standingCharge}
              disabled={readOnly}
              onChange={(event) => setStandingCharge(event.target.value)}
              className="solar-input"
            />
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={includeStandingCharge}
              disabled={readOnly}
              onChange={(event) => setIncludeStandingCharge(event.target.checked)}
            />
            Include standing charge in daily savings
          </label>
        </div>

        <div className="space-y-4">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
            Cheap / peak windows
          </h3>
          <p className="text-xs text-[var(--muted)]">
            Used to split import into off-peak vs peak for savings breakdown and warnings.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm font-medium">
              Off-peak start
              <input
                type="time"
                value={offPeakStart}
                disabled={readOnly}
                onChange={(event) => setOffPeakStart(event.target.value)}
                className="solar-input"
              />
            </label>
            <label className="block text-sm font-medium">
              Off-peak end
              <input
                type="time"
                value={offPeakEnd}
                disabled={readOnly}
                onChange={(event) => setOffPeakEnd(event.target.value)}
                className="solar-input"
              />
            </label>
            <label className="block text-sm font-medium">
              Peak start
              <input
                type="time"
                value={peakStart}
                disabled={readOnly}
                onChange={(event) => setPeakStart(event.target.value)}
                className="solar-input"
              />
            </label>
            <label className="block text-sm font-medium">
              Peak end
              <input
                type="time"
                value={peakEnd}
                disabled={readOnly}
                onChange={(event) => setPeakEnd(event.target.value)}
                className="solar-input"
              />
            </label>
          </div>
        </div>

        <div className="space-y-4">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
            Battery assumptions
          </h3>
          <label className="block text-sm font-medium">
            Battery capacity (kWh)
            <input
              type="number"
              step="0.1"
              min="0"
              max="100"
              value={batteryCapacity}
              disabled={readOnly}
              onChange={(event) => setBatteryCapacity(event.target.value)}
              className="solar-input"
            />
          </label>
          <label className="block text-sm font-medium">
            Minimum reserve (%)
            <input
              type="number"
              step="1"
              min="0"
              max="100"
              value={batteryMinReserve}
              disabled={readOnly}
              onChange={(event) => setBatteryMinReserve(event.target.value)}
              className="solar-input"
            />
          </label>
          <label className="block text-sm font-medium">
            Maximum charge (%)
            <input
              type="number"
              step="1"
              min="0"
              max="100"
              value={maximumCharge}
              disabled={readOnly}
              onChange={(event) => setMaximumCharge(event.target.value)}
              className="solar-input"
            />
          </label>
        </div>

        <div className="space-y-4">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
            Warning thresholds
          </h3>
          <label className="block text-sm font-medium">
            Peak import warning (W)
            <input
              type="number"
              step="50"
              min="0"
              max="10000"
              value={warningImportThreshold}
              disabled={readOnly}
              onChange={(event) => setWarningImportThreshold(event.target.value)}
              className="solar-input"
            />
          </label>
          <label className="block text-sm font-medium">
            High battery SOC warning (%)
            <input
              type="number"
              step="1"
              min="0"
              max="100"
              value={warningBatterySoc}
              disabled={readOnly}
              onChange={(event) => setWarningBatterySoc(event.target.value)}
              className="solar-input"
            />
          </label>
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

        {!readOnly ? (
          <button type="submit" disabled={submitting} className="solar-btn-primary">
            Review change
          </button>
        ) : null}
      </form>

      <ConfirmDialog
        open={confirmOpen}
        title="Confirm tariff change"
        description="Update electricity rates, windows, and battery assumptions used for savings calculations?"
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => void handleSubmit()}
      />
    </section>
  );
}
