"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { AssistantPanel } from "@/components/ai/AssistantPanel";
import { AppShell } from "@/components/shared/AppShell";
import { PageHeader } from "@/components/shared/PageHeader";
import { BoltIcon } from "@/components/shared/icons";
import { useAuth } from "@/lib/auth-context";
import { canWrite } from "@/lib/permissions";

export default function AssistantPage() {
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
      return;
    }
    if (!loading && user && !canWrite(user)) {
      router.replace("/");
    }
  }, [loading, user, router]);

  if (loading || !user || !canWrite(user)) {
    return null;
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Assistant"
          icon={<BoltIcon size={22} />}
          title="AI Assistant"
          description="Ask about your system and get optimisation suggestions. Any change is proposed for you to confirm and is fully audited."
        />
        <AssistantPanel />
      </div>
    </AppShell>
  );
}
