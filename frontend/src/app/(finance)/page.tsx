"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { BankImportCard } from "@/components/finance/BankImportCard";
import { FinanceAiAnalystCard } from "@/components/finance/FinanceAiAnalystCard";
import { FinanceOverviewView } from "@/components/finance/FinanceOverviewView";
import { SavedFiguresBanner } from "@/components/finance/SavedFiguresBanner";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { WidgetErrorBoundary } from "@/components/shared/WidgetErrorBoundary";
import { ErrorBanner, SuccessBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { canWrite } from "@/lib/permissions";
import { useFinanceOverview } from "@/lib/use-finance-overview";

export default function FinanceOverviewPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { overview, loading, refreshing, error, refresh, reload } = useFinanceOverview(user);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login");
    }
  }, [authLoading, user, router]);

  if (authLoading || !user) {
    return <AuthLoadingShell />;
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Overview"
        description="Personal and business finances at a glance — balances, debts, cash flow, and alerts."
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
        <FinanceAiAnalystCard user={user} />
      </div>
      {loading && !overview ? (
        <p className="mt-8 text-sm text-[var(--muted)]">Loading finance overview…</p>
      ) : overview ? (
        <div className="mt-6">
          <SavedFiguresBanner
            refreshing={refreshing}
            generatedAt={overview.generated_at}
            cached={overview.cached}
            quickfileSyncedAt={overview.quickfile_synced_at}
            lunchflowSyncedAt={overview.lunchflow_synced_at}
          />
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
