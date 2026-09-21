"use client";

import { useEffect, useState } from "react";

import { FinanceHealthPanel } from "@/components/finance/FinanceHealthPanel";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { PageHeader } from "@/components/shared/PageHeader";
import { FundingCircleSettingsPanel } from "@/components/settings/FundingCircleSettingsPanel";
import { LunchFlowSettingsPanel } from "@/components/settings/LunchFlowSettingsPanel";
import { QuickFileSettingsPanel } from "@/components/settings/QuickFileSettingsPanel";
import { useRequireAuth } from "@/lib/use-require-auth";
import { canWrite } from "@/lib/permissions";

/**
 * Connections — progressive per-provider status.
 *
 * Prod evidence (dpl_3DyAZh5): the browser correctly calls
 * `/backend/finance/...` (NEXT_PUBLIC_API_BASE_URL defaults to `/backend`).
 * Bare `/finance/health` on the Next host 404s and is not the client path.
 * Previous batched `connection-status` + `deferOwnStatusLoad` still left
 * panels spinning when Neon/lifespan stalled past the client abort.
 *
 * Each panel loads its own status independently and fails soft so LF/QF/FC
 * can leave Loading without waiting on each other. A post-mount gate keeps
 * SSR and the first client paint identical (AuthLoadingShell) to avoid
 * React #418 remount loops that re-trigger status fetches.
 */
export default function ConnectBanksPage() {
  const { user, gated, redirecting } = useRequireAuth();
  const [clientReady, setClientReady] = useState(false);

  useEffect(() => {
    setClientReady(true);
  }, []);

  // SSR + hydrate: same shell. After mount, gate on auth as usual.
  if (!clientReady || gated) {
    return <AuthLoadingShell redirecting={redirecting} />;
  }

  const readOnly = !canWrite(user);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Connections"
        description="Are QuickFile and Lunch Flow working? How current is each figure? Fix anything that needs you here."
      />
      <div className="mt-6 space-y-8">
        {/* LF/QF first — never queued behind finance health. */}
        <section aria-labelledby="lunchflow-heading">
          <h2 id="lunchflow-heading" className="solar-section-title">
            Lunch Flow
          </h2>
          <div className="mt-4">
            <LunchFlowSettingsPanel readOnly={readOnly} />
          </div>
        </section>
        <section aria-labelledby="quickfile-heading">
          <h2 id="quickfile-heading" className="solar-section-title">
            QuickFile
          </h2>
          <div className="mt-4">
            <QuickFileSettingsPanel readOnly={readOnly} />
          </div>
        </section>
        <section aria-labelledby="funding-circle-heading">
          <h2 id="funding-circle-heading" className="solar-section-title">
            Funding Circle
          </h2>
          <div className="mt-4">
            <FundingCircleSettingsPanel readOnly={readOnly} />
          </div>
        </section>
        <FinanceHealthPanel canEdit={!readOnly} />
      </div>
    </AppShell>
  );
}
