"use client";

import { useState } from "react";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { tariffSettingsSchema, type TariffSettings } from "@/lib/schemas";

type TariffSettingsFormProps = {
  initial: TariffSettings;
  readOnly?: boolean;
  onSubmit: (tariff: TariffSettings) => Promise<void>;
};

export function TariffSettingsForm({
  initial,
  readOnly = false,
  onSubmit,
}: TariffSettingsFormProps) {
  const [importRate, setImportRate] = useState(String(initial.import_rate));
  const [exportRate, setExportRate] = useState(String(initial.export_rate));
  const [currency, setCurrency] = useState(initial.currency);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const buildPayload = (): TariffSettings | null => {
    const result = tariffSettingsSchema.safeParse({
      import_rate: Number(importRate),
      export_rate: Number(exportRate),
      currency: currency.toUpperCase(),
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
        Import and export rates used for savings calculations.
      </p>

      <form
        className="mt-4 space-y-4"
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
        description="Update electricity import/export rates used for savings calculations?"
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => void handleSubmit()}
      />
    </section>
  );
}
