"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { FinanceAlertsPanel } from "@/components/finance/FinanceAlertsPanel";
import { FinanceConnectBanner } from "@/components/finance/FinanceConnectBanner";
import { FinanceOverviewView } from "@/components/finance/FinanceOverviewView";
import { FinanceAiAdviceCard } from "@/components/finance/FinanceAiAdviceCard";
import { RecentTransactions } from "@/components/finance/RecentTransactions";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import {
  bankConnectionsResponseSchema,
  lunchFlowConfigStatusSchema,
  openBankingConfigStatusSchema,
  type BankConnectionItem,
} from "@/lib/finance-schemas";
import { useFinanceOverview } from "@/lib/use-finance-overview";
import { canWrite } from "@/lib/permissions";

export default function FinanceOverviewPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { overview, accounts, liabilities, loading, error, refresh } =
    useFinanceOverview(Boolean(user));
  const [bankConnections, setBankConnections] = useState<BankConnectionItem[]>([]);
  const [obConfigured, setObConfigured] = useState(true);
  const [obReady, setObReady] = useState<boolean | null>(null);
  const [lunchFlowActive, setLunchFlowActive] = useState(false);

  useEffect(() => {
    if (!user) return;
    void (async () => {
      try {
        const [cards, ob, lunchFlow] = await Promise.all([
          apiClient.get<unknown>("/finance/bank-connections"),
          apiClient.get<unknown>("/finance/integrations/open-banking/status"),
          apiClient.get<unknown>("/finance/integrations/lunch-flow/status"),
        ]);
        setBankConnections(bankConnectionsResponseSchema.parse(cards).connections);
        const parsedOb = openBankingConfigStatusSchema.parse(ob);
        setObConfigured(parsedOb.configured);
        setObReady(parsedOb.provider_ready ?? null);
        setLunchFlowActive(lunchFlowConfigStatusSchema.parse(lunchFlow).configured);
      } catch {
        setBankConnections([]);
      }
    })();
  }, [user, overview]);

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
            Refresh
          </button>
        }
      />
      {error ? <div className="mt-4"><ErrorBanner message={error} /></div> : null}
      {loading && !overview ? (
        <p className="mt-8 text-sm text-[var(--muted)]">Loading finance overview…</p>
      ) : overview ? (
        <div className="mt-6 space-y-8">
          <FinanceConnectBanner
            connections={bankConnections}
            obConfigured={obConfigured}
            obReady={obReady}
            lunchFlowActive={lunchFlowActive}
          />
          <FinanceAlertsPanel insights={overview.insights} />
          <FinanceAiAdviceCard canUse={canWrite(user)} />
          <FinanceOverviewView
            overview={overview}
            accounts={accounts}
            liabilities={liabilities}
          />
          <section>
            <h2 className="mb-3 text-lg font-semibold">Recent transactions</h2>
            <RecentTransactions limit={10} />
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
