"use client";

import { QuickFileSettingsPanel } from "@/components/settings/QuickFileSettingsPanel";

const integrations = [
  { id: "manual", label: "Manual entry", status: "Active", detail: "Enter balances and transactions yourself." },
  { id: "open_banking", label: "Open Banking", status: "Coming soon", detail: "No bank passwords stored — OAuth when enabled." },
  { id: "octopus", label: "Octopus Energy", status: "Active", detail: "Configured in Energy settings." },
  { id: "sunsynk", label: "Sunsynk Connect", status: "Active", detail: "Live inverter data in Energy section." },
  { id: "tesla", label: "Tesla", status: "Coming soon", detail: "EV charging visibility when API is connected." },
];

type FinanceSettingsPanelProps = {
  readOnly?: boolean;
};

export function FinanceSettingsPanel({ readOnly = false }: FinanceSettingsPanelProps) {
  return (
    <div className="space-y-6">
      <QuickFileSettingsPanel readOnly={readOnly} />
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
