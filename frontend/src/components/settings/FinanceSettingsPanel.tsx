"use client";

import { Suspense, useState } from "react";

import { LunchFlowSettingsForm } from "@/components/finance/LunchFlowSettingsForm";
import { OpenBankingSettingsPanel } from "@/components/settings/OpenBankingSettingsPanel";
import { QuickFileSettingsPanel } from "@/components/settings/QuickFileSettingsPanel";
import { apiClient } from "@/lib/api-client";
import { financeIntegrationsReconnectResultSchema } from "@/lib/finance-schemas";

const integrations = [
  { id: "manual", label: "Manual entry", status: "Active", detail: "Enter balances and transactions yourself." },
  { id: "octopus", label: "Octopus Energy", status: "Active", detail: "Configured in Energy settings." },
  { id: "sunsynk", label: "Sunsynk Connect", status: "Active", detail: "Live inverter data in Energy section." },
];

type FinanceSettingsPanelProps = {
  readOnly?: boolean;
};

function OpenBankingSettingsPanelFallback() {
  return (
    <section className="solar-card">
      <p className="text-sm text-[var(--muted)]">Loading Open Banking settings…</p>
    </section>
  );
}

export function FinanceSettingsPanel({ readOnly = false }: FinanceSettingsPanelProps) {
  const [reconnectBusy, setReconnectBusy] = useState(false);
  const [reconnectMessage, setReconnectMessage] = useState<string | null>(null);
  const [reconnectError, setReconnectError] = useState<string | null>(null);
  const [lunchFlowKey, setLunchFlowKey] = useState(0);
  const [quickFileKey, setQuickFileKey] = useState(0);

  async function reconnectFromHostedKeys() {
    setReconnectBusy(true);
    setReconnectMessage(null);
    setReconnectError(null);
    try {
      const data = await apiClient.post<unknown>("/finance/integrations/reconnect");
      const result = financeIntegrationsReconnectResultSchema.parse(data);
      setReconnectMessage(result.message);
      setQuickFileKey((value) => value + 1);
      setLunchFlowKey((value) => value + 1);
    } catch (err) {
      setReconnectError(err instanceof Error ? err.message : "Reconnect failed");
    } finally {
      setReconnectBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      {!readOnly ? (
        <section className="solar-card space-y-3">
          <div>
            <h2 className="text-lg font-semibold">Hosted keys</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Reload QuickFile and Lunch Flow from the Vercel environment if Settings shows them as
              disconnected after a deploy.
            </p>
          </div>
          {reconnectError ? (
            <p className="rounded-lg border border-red-300/40 bg-red-500/10 px-3 py-2 text-sm text-red-800 dark:text-red-200">
              {reconnectError}
            </p>
          ) : null}
          {reconnectMessage ? (
            <p className="rounded-lg border border-emerald-300/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-900 dark:text-emerald-200">
              {reconnectMessage}
            </p>
          ) : null}
          <button
            type="button"
            className="solar-btn-secondary"
            disabled={reconnectBusy}
            onClick={() => void reconnectFromHostedKeys()}
          >
            {reconnectBusy ? "Reconnecting…" : "Reconnect QuickFile & Lunch Flow"}
          </button>
        </section>
      ) : null}
      <QuickFileSettingsPanel key={quickFileKey} readOnly={readOnly} />
      <LunchFlowSettingsForm key={lunchFlowKey} readOnly={readOnly} />
      <Suspense fallback={<OpenBankingSettingsPanelFallback />}>
        <OpenBankingSettingsPanel readOnly={readOnly} />
      </Suspense>
      <section className="solar-card space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Other integrations</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Additional providers will appear here as they are enabled.
          </p>
        </div>
        <ul className="grid gap-3 sm:grid-cols-2">
          {integrations.map((item) => (
            <li key={item.id} className="rounded-xl border border-[var(--border)] p-4">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{item.label}</span>
                <span className="text-xs uppercase tracking-wide text-[var(--muted)]">{item.status}</span>
              </div>
              <p className="mt-2 text-sm text-[var(--muted)]">{item.detail}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
