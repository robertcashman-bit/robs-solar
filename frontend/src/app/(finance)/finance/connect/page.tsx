"use client";

import { FinanceHealthPanel } from "@/components/finance/FinanceHealthPanel";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { PageHeader } from "@/components/shared/PageHeader";
import { FundingCircleSettingsPanel } from "@/components/settings/FundingCircleSettingsPanel";
import { LunchFlowSettingsPanel } from "@/components/settings/LunchFlowSettingsPanel";
import { QuickFileSettingsPanel } from "@/components/settings/QuickFileSettingsPanel";
import { useAuth } from "@/lib/auth-context";
import { useConnectionStatuses } from "@/lib/use-connection-statuses";
import { useRequireAuth } from "@/lib/use-require-auth";
import { canWrite } from "@/lib/permissions";

export default function ConnectBanksPage() {
  const { user, gated, redirecting } = useRequireAuth();
  const { authResolved } = useAuth();
  const { statuses, error: statusError } = useConnectionStatuses(user, authResolved);

  if (gated) return <AuthLoadingShell redirecting={redirecting} />;

  const readOnly = !canWrite(user);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Connections"
        description="Are QuickFile and Lunch Flow working? How current is each figure? Fix anything that needs you here."
      />
      <div className="mt-6 space-y-8">
        <FinanceHealthPanel canEdit={!readOnly} />
        <section aria-labelledby="lunchflow-heading">
          <h2 id="lunchflow-heading" className="solar-section-title">
            Lunch Flow
          </h2>
          <div className="mt-4">
            <LunchFlowSettingsPanel
              readOnly={readOnly}
              initialStatus={statuses?.lunchflow ?? null}
              statusError={statusError}
              deferOwnStatusLoad
            />
          </div>
        </section>
        <section aria-labelledby="quickfile-heading">
          <h2 id="quickfile-heading" className="solar-section-title">
            QuickFile
          </h2>
          <div className="mt-4">
            <QuickFileSettingsPanel
              readOnly={readOnly}
              initialStatus={statuses?.quickfile ?? null}
              statusError={statusError}
              deferOwnStatusLoad
            />
          </div>
        </section>
        <section aria-labelledby="funding-circle-heading">
          <h2 id="funding-circle-heading" className="solar-section-title">
            Funding Circle
          </h2>
          <div className="mt-4">
            <FundingCircleSettingsPanel
              readOnly={readOnly}
              initialStatus={statuses?.funding_circle ?? null}
              statusError={statusError}
              deferOwnStatusLoad
            />
          </div>
        </section>
      </div>
    </AppShell>
  );
}
