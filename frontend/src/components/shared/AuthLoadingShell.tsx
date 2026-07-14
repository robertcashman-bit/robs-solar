import { AppShell } from "@/components/shared/AppShell";
import { PageLoading } from "@/components/shared/PageLoading";

export function AuthLoadingShell() {
  return (
    <AppShell>
      <PageLoading label="Loading session" rows={2} />
    </AppShell>
  );
}
