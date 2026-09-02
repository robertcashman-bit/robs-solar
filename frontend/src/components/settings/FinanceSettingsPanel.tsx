"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { BankImportCard } from "@/components/finance/BankImportCard";
import { CategoryRulesPanel } from "@/components/finance/CategoryRulesPanel";
import { FinanceExportPanel } from "@/components/finance/FinanceExportPanel";
import { FinanceHealthPanel } from "@/components/finance/FinanceHealthPanel";
import { AppShortcutPanel } from "@/components/settings/AppShortcutPanel";
import { FundingCircleSettingsPanel } from "@/components/settings/FundingCircleSettingsPanel";
import { LunchFlowSettingsPanel } from "@/components/settings/LunchFlowSettingsPanel";
import { OpenBankingSettingsPanel } from "@/components/settings/OpenBankingSettingsPanel";
import { QuickFileSettingsPanel } from "@/components/settings/QuickFileSettingsPanel";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { financeIntegrationSchema, oidcStatusSchema, type FinanceIntegration } from "@/lib/finance-schemas";

const STATIC_INTEGRATIONS: FinanceIntegration[] = [
  { id: "manual", label: "Manual entry", status: "active" },
];

type FinanceSettingsPanelProps = {
  readOnly?: boolean;
};

function statusLabel(status: string): string {
  if (status === "active") return "Active";
  if (status === "inactive") return "Not connected";
  return status;
}

function isActive(
  byId: Record<string, FinanceIntegration | undefined>,
  id: string,
): boolean {
  return byId[id]?.status === "active";
}

export function FinanceSettingsPanel({ readOnly = false }: FinanceSettingsPanelProps) {
  const { user } = useAuth();
  const [integrations, setIntegrations] = useState<FinanceIntegration[]>(STATIC_INTEGRATIONS);
  const [oidcEnabled, setOidcEnabled] = useState(false);

  useEffect(() => {
    if (!user) return;
    void (async () => {
      try {
        const [providerData, oidcData] = await Promise.all([
          apiClient.get<unknown>("/finance/integrations"),
          apiClient.get<unknown>("/auth/oidc/status"),
        ]);
        const providers = financeIntegrationSchema
          .array()
          .parse(providerData)
          .filter((item) => !["octopus", "sunsynk", "tesla"].includes(item.id));
        setIntegrations([
          ...providers,
          ...STATIC_INTEGRATIONS.filter((s) => !providers.some((p) => p.id === s.id)),
        ]);
        setOidcEnabled(oidcStatusSchema.parse(oidcData).enabled);
      } catch {
        setIntegrations(STATIC_INTEGRATIONS);
      }
    })();
  }, [user]);

  const byId = Object.fromEntries(integrations.map((item) => [item.id, item]));
  const banksLive = isActive(byId, "lunchflow") || isActive(byId, "open_banking");
  const liveBits = [
    "App login and manual finance accounts",
    isActive(byId, "quickfile") ? "QuickFile" : null,
    isActive(byId, "lunchflow") ? "Lunch Flow" : null,
    isActive(byId, "open_banking") ? "TrueLayer" : null,
    isActive(byId, "funding_circle") ? "Funding Circle" : null,
  ].filter((item): item is string => Boolean(item));
  const missing = [
    isActive(byId, "quickfile") ? null : "QuickFile",
    banksLive ? null : "Lunch Flow (or TrueLayer)",
  ].filter((item): item is string => Boolean(item));
  const optionalBits = [
    banksLive && !isActive(byId, "open_banking")
      ? "TrueLayer is optional while Lunch Flow is connected"
      : null,
    isActive(byId, "funding_circle") ? null : "Funding Circle loan figure (optional)",
  ].filter((item): item is string => Boolean(item));

  return (
    <div className="space-y-6">
      <section className="solar-card space-y-3">
        <h2 className="text-lg font-semibold">What&apos;s connected</h2>
        <p className="text-sm text-[var(--muted)]">
          QuickFile and Lunch Flow are the live connections for this app. TrueLayer
          is only needed if you want a second bank login. The same setup also lives on{" "}
          <Link href="/finance/connect" className="underline underline-offset-2">
            Connections
          </Link>
          . Production health may still show a leftover solar adapter_mode — that does
          not mean your money figures are simulated.
        </p>
        <ul className="space-y-2 text-sm">
          <li>
            <span className="font-medium text-emerald-600 dark:text-emerald-400">Live — </span>
            {liveBits.join(", ")}.
          </li>
          {missing.length > 0 ? (
            <li>
              <span className="font-medium text-amber-600 dark:text-amber-400">Needs setup — </span>
              {missing.join(", ")}.
            </li>
          ) : null}
          {optionalBits.length > 0 ? (
            <li>
              <span className="font-medium text-[var(--muted)]">Optional — </span>
              {optionalBits.join("; ")}.
            </li>
          ) : null}
        </ul>
        <ol className="list-decimal space-y-2 pl-5 text-sm">
          <li>
            <span className="font-medium">QuickFile</span> — business bank and unpaid invoices.
            If Custody Note already has QuickFile, double-click{" "}
            <strong>Connect Personal Finance</strong> on this Mac, or paste the three
            fields below.
          </li>
          <li>
            <span className="font-medium">Lunch Flow</span> — paste the Lunch Flow Destinations
            → API key below, then Test / Sync. Banks stay connected in Lunch Flow; this app
            only needs the key.
          </li>
          <li>
            <span className="font-medium">TrueLayer</span> — one-time Client ID, secret, and
            redirect URI, then Log in to your bank.
          </li>
          <li>
            <span className="font-medium">Funding Circle</span> — enter the outstanding loan
            below, or pull it after a TrueLayer sync.
          </li>
        </ol>
      </section>
      <FinanceHealthPanel canEdit={!readOnly} />
      <AppShortcutPanel />
      <BankImportCard readOnly={readOnly} showSettingsLink={false} />
      <OpenBankingSettingsPanel readOnly={readOnly} />
      <LunchFlowSettingsPanel readOnly={readOnly} />
      <FundingCircleSettingsPanel readOnly={readOnly} />
      <QuickFileSettingsPanel readOnly={readOnly} />
      <section className="solar-card space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Integration overview</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Provider status from the backend. Configure credentials in the panels above.
          </p>
        </div>
        <ul className="grid gap-3 sm:grid-cols-2">
          {integrations.map((item) => (
            <li key={item.id} className="rounded-xl border border-[var(--border)] p-4">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{item.label}</span>
                <span
                  className={`text-xs uppercase tracking-wide ${
                    item.status === "active"
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-[var(--muted)]"
                  }`}
                >
                  {statusLabel(item.status)}
                </span>
              </div>
            </li>
          ))}
          <li className="rounded-xl border border-[var(--border)] p-4">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium">SSO (OIDC)</span>
              <span className="text-xs uppercase tracking-wide text-[var(--muted)]">
                {oidcEnabled ? "Active" : "Off"}
              </span>
            </div>
            <p className="mt-2 text-sm text-[var(--muted)]">
              {oidcEnabled
                ? "Sign in via your identity provider at /backend/auth/oidc/login"
                : "Set OIDC_* env vars on the backend to enable."}
            </p>
          </li>
        </ul>
      </section>
      <CategoryRulesPanel canEdit={!readOnly} />
      <FinanceExportPanel />
    </div>
  );
}
