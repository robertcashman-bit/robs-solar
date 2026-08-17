"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { BankImportCard } from "@/components/finance/BankImportCard";
import { FinanceOverviewView } from "@/components/finance/FinanceOverviewView";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner, SuccessBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { canWrite } from "@/lib/permissions";
import { useFinanceOverview } from "@/lib/use-finance-overview";

export default function FinanceOverviewPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { overview, loading, refreshing, error, refresh } = useFinanceOverview(user);
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
      <div className="mt-4">
        <BankImportCard
          readOnly={!canWrite(user)}
          autoImport={canWrite(user)}
          onImported={(text) => {
            setStatus(text);
            void refresh();
          }}
        />
      </div>
      {loading && !overview ? (
        <p className="mt-8 text-sm text-[var(--muted)]">Loading finance overview…</p>
      ) : overview ? (
        <div className="mt-6">
          {refreshing ? (
            <p className="mb-3 text-sm text-[var(--muted)]">
              Showing saved figures — pulling latest from QuickFile and Lunch Flow…
            </p>
          ) : null}
          <FinanceOverviewView
            overview={overview}
            onDismissInsight={
              canWrite(user)
                ? async (id) => {
                    try {
                      await apiClient.post(`/finance/insights/${id}/dismiss`);
                      setStatus("Alert dismissed");
                      await refresh();
                    } catch (err) {
                      setStatus(err instanceof Error ? err.message : "Failed to dismiss alert");
                    }
                  }
                : undefined
            }
          />
        </div>
      ) : null}
    </AppShell>
  );
}
