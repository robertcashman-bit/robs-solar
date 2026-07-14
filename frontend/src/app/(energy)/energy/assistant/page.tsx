"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { AssistantPanel } from "@/components/ai/AssistantPanel";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { PageHeader } from "@/components/shared/PageHeader";
import { BoltIcon } from "@/components/shared/icons";
import { useAuth } from "@/lib/auth-context";

export default function AssistantPage() {
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  if (loading) {
    return <AuthLoadingShell />;
  }

  if (!user) {
    return null;
  }

  return (
    <AppShell>
      <div className="solar-page">
        <PageHeader
          eyebrow="Assistant"
          icon={<BoltIcon size={22} />}
          title="AI Assistant"
          description="Ask about your system and get optimisation suggestions. Advice only — this app never applies changes to the inverter."
        />
        <AssistantPanel adviceOnly />
      </div>
    </AppShell>
  );
}
