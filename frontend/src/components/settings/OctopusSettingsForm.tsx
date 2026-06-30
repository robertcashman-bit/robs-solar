"use client";

import { useState } from "react";

import { apiClient } from "@/lib/api-client";
import {
  octopusConfigStatusSchema,
  octopusDiscoverResultSchema,
  type OctopusConfigStatus,
} from "@/lib/schemas";

type OctopusSettingsFormProps = {
  initial: OctopusConfigStatus;
  readOnly?: boolean;
  onSaved?: (status: OctopusConfigStatus) => void;
};

export function OctopusSettingsForm({ initial, readOnly = false, onSaved }: OctopusSettingsFormProps) {
  const [apiKey, setApiKey] = useState("");
  const [accountNumber, setAccountNumber] = useState(initial.account_number);
  const [mpan, setMpan] = useState(initial.mpan);
  const [meterSerial, setMeterSerial] = useState(initial.meter_serial);
  const [region, setRegion] = useState(initial.region || "C");
  const [keyAlreadySet, setKeyAlreadySet] = useState(initial.api_key_set);

  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [discovering, setDiscovering] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleDiscover = async () => {
    setError(null);
    setSuccess(null);
    if (!apiKey && !keyAlreadySet) {
      setError("Enter your API key first (sk_live_...).");
      return;
    }
    if (!accountNumber) {
      setError("Enter your account number (A-XXXXXXXX) first.");
      return;
    }
    setDiscovering(true);
    try {
      const data = await apiClient.post<unknown>("/octopus/discover", {
        api_key: apiKey || undefined,
        account_number: accountNumber,
      });
      const result = octopusDiscoverResultSchema.parse(data);
      setMpan(result.mpan);
      setMeterSerial(result.meter_serial);
      if (result.region) {
        setRegion(result.region);
      }
      setSuccess("Found your meter details. Review and save.");
    } catch (discoverError) {
      setError(discoverError instanceof Error ? discoverError.message : "Discovery failed");
    } finally {
      setDiscovering(false);
    }
  };

  const handleSave = async () => {
    setError(null);
    setSuccess(null);
    setSaving(true);
    try {
      const data = await apiClient.put<unknown>("/octopus/settings", {
        api_key: apiKey,
        account_number: accountNumber,
        mpan,
        meter_serial: meterSerial,
        region: region.toUpperCase().slice(0, 1),
      });
      const status = octopusConfigStatusSchema.parse(data);
      setKeyAlreadySet(status.api_key_set);
      setApiKey("");
      setSuccess("Octopus settings saved. Live prices will update shortly.");
      onSaved?.(status);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="solar-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Octopus Energy</h2>
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
            initial.configured
              ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
              : "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
          }`}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${initial.configured ? "bg-emerald-500" : "bg-amber-500"}`}
          />
          {initial.configured ? "Connected" : "Not configured"}
        </span>
      </div>
      <p className="mt-1 text-sm text-[var(--muted)]">
        Connects live Agile prices and consumption. Get your API key from octopus.energy &rarr;
        Personal Details &rarr; API access. Your password is never stored.
      </p>

      <form
        className="mt-4 space-y-4"
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          if (!readOnly) {
            void handleSave();
          }
        }}
      >
        <label className="block text-sm font-medium">
          API key {keyAlreadySet ? <span className="text-[var(--muted)]">(saved — leave blank to keep)</span> : null}
          <input
            type="password"
            autoComplete="off"
            placeholder={keyAlreadySet ? "••••••••••••" : "sk_live_..."}
            value={apiKey}
            disabled={readOnly}
            onChange={(event) => setApiKey(event.target.value)}
            className="solar-input"
          />
        </label>
        <label className="block text-sm font-medium">
          Account number
          <input
            type="text"
            placeholder="A-XXXXXXXX"
            value={accountNumber}
            disabled={readOnly}
            onChange={(event) => setAccountNumber(event.target.value.toUpperCase())}
            className="solar-input"
          />
        </label>

        {!readOnly ? (
          <button
            type="button"
            onClick={() => void handleDiscover()}
            disabled={discovering}
            className="solar-btn-ghost"
          >
            {discovering ? "Looking up…" : "Test & auto-discover meter"}
          </button>
        ) : null}

        <div className="grid gap-4 sm:grid-cols-3">
          <label className="block text-sm font-medium sm:col-span-2">
            MPAN
            <input
              type="text"
              value={mpan}
              disabled={readOnly}
              onChange={(event) => setMpan(event.target.value)}
              className="solar-input"
            />
          </label>
          <label className="block text-sm font-medium">
            Region
            <input
              type="text"
              maxLength={1}
              value={region}
              disabled={readOnly}
              onChange={(event) => setRegion(event.target.value.toUpperCase())}
              className="solar-input"
            />
          </label>
        </div>
        <label className="block text-sm font-medium">
          Meter serial
          <input
            type="text"
            value={meterSerial}
            disabled={readOnly}
            onChange={(event) => setMeterSerial(event.target.value)}
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
          <button type="submit" disabled={saving} className="solar-btn-primary">
            {saving ? "Saving…" : "Save Octopus settings"}
          </button>
        ) : null}
      </form>
    </section>
  );
}
