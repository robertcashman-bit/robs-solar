"use client";

import { useState } from "react";

import { BankImportCard } from "@/components/finance/BankImportCard";
import { FinanceOverviewView } from "@/components/finance/FinanceOverviewView";
import { SavedFiguresBanner } from "@/components/finance/SavedFiguresBanner";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { WidgetErrorBoundary } from "@/components/shared/WidgetErrorBoundary";
import { ErrorBanner, SuccessBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { apiClient } from "@/lib/api-client";
import { useRequireAuth } from "@/lib/use-require-auth";
import { canWrite } from "@/lib/permissions";
import { FinancePeriodScopeControl } from "@/components/finance/FinancePeriodScopeControl";
import { overviewDefaultPeriod } from "@/lib/finance-period";
import { useFinanceOverview } from "@/lib/use-finance-overview";
import { useFinancePeriod } from "@/lib/use-finance-period";

export default function FinanceOverviewPage() {
  const { user, gated, redirecting } = useRequireAuth();
  const defaultPeriod = overviewDefaultPeriod();
  const periodState = useFinancePeriod({
    dualPeriod: true,
    defaultScope: "both",
    defaultPeriod,
    preferDefaultPeriod: true,
  });
  const { overview, loading, refreshing, error, refresh, reload } = useFinanceOverview(user, {
    personalPeriod: periodState.personalPeriod,
    businessPeriod: periodState.businessPeriod,
  });
  const [status, setStatus] = useState<string | null>(null);


  if (gated) {
    return <AuthLoadingShell redirecting={redirecting} />;
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Overview"
        description="What you own, what you owe, and what's left — You and Defence Legal."
        actions={
          <button type="button" className="solar-btn-secondary text-sm" onClick={() => void refresh()}>
            {refreshing ? "Updating…" : "Refresh"}
          </button>
        }
      />
      {error ? <div className="mt-4"><ErrorBanner message={error} /></div> : null}
      {status ? <div className="mt-4"><SuccessBanner message={status} /></div> : null}
      <div className="mt-4 space-y-4">
        <BankImportCard
          readOnly={!canWrite(user)}
          autoImport={false}
          deferMs={2000}
          onImported={(text) => {
            setStatus(text);
            void refresh();
          }}
        />
      </div>
      {loading && !overview ? (
        <p className="mt-8 text-sm text-[var(--muted)]">Loading saved figures…</p>
      ) : overview ? (
        <div className="mt-6">
          <SavedFiguresBanner
            refreshing={refreshing}
            generatedAt={overview.generated_at}
            cached={overview.cached}
            quickfileSyncedAt={overview.quickfile_synced_at}
            lunchflowSyncedAt={overview.lunchflow_synced_at}
          />
          <div className="mb-6">
            <FinancePeriodScopeControl
              dualPeriod
              period={periodState.period}
              personalPeriod={periodState.personalPeriod}
              businessPeriod={periodState.businessPeriod}
              onPeriodChange={periodState.setPeriod}
              onPersonalPeriodChange={periodState.setPersonalPeriod}
              onBusinessPeriodChange={periodState.setBusinessPeriod}
              showScope={false}
              periodKeys={["mtd", "1m", "3m", "6m", "12m"]}
              coverageNote={
                [overview.personal_period_flow?.coverage_note, overview.business_period_flow?.coverage_note]
                  .filter(Boolean)
                  .join(" ")
                || null
              }
            />
          </div>
          <WidgetErrorBoundary fallback="Unable to load dashboard figures.">
          <FinanceOverviewView
            overview={overview}
            onDismissInsight={
              canWrite(user)
                ? async (id) => {
                    try {
                      await apiClient.post(`/finance/insights/${id}/dismiss`);
                      setStatus("Alert dismissed");
                      await reload();
                    } catch (err) {
                      setStatus(err instanceof Error ? err.message : "Failed to dismiss alert");
                    }
                  }
                : undefined
            }
          />
          </WidgetErrorBoundary>
        </div>
      ) : null}
    </AppShell>
  );
}
