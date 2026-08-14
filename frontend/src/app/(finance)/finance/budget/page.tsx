"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { BudgetPlanView } from "@/components/finance/BudgetPlanView";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner, SuccessBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { PageLoading } from "@/components/shared/PageLoading";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import {
  budgetPlanSchema,
  budgetSuggestionsSchema,
  type BudgetPlan,
  type BudgetPlanItem,
  type BudgetSuggestions,
} from "@/lib/finance-schemas";
import { canWrite } from "@/lib/permissions";

export default function BudgetPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [suggestions, setSuggestions] = useState<BudgetSuggestions | null>(null);
  const [initialPlan, setInitialPlan] = useState<BudgetPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<unknown>("/finance/budget-plans/suggestions");
      const parsed = budgetSuggestionsSchema.parse(data);
      setSuggestions(parsed);
      if (parsed.active_plan_id) {
        const planData = await apiClient.get<unknown>(`/finance/budget-plans/${parsed.active_plan_id}`);
        setInitialPlan(budgetPlanSchema.parse(planData));
      } else {
        setInitialPlan(null);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load budget");
      setSuggestions(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [user, load, reloadKey]);

  async function save(payload: {
    name: string;
    strategy: "stabilise" | "balanced" | "debt_attack" | "custom";
    items: BudgetPlanItem[];
    fingerprint: string;
    activate: boolean;
    planId: number | null;
  }) {
    setSaving(true);
    setSuccess(null);
    setError(null);
    try {
      const body = {
        name: payload.name,
        strategy: payload.planId ? "custom" : payload.strategy,
        items: payload.items,
        source_fingerprint: payload.fingerprint,
        activate: payload.activate,
        notes: "",
      };
      const saved = payload.planId
        ? await apiClient.put<unknown>(`/finance/budget-plans/${payload.planId}`, body)
        : await apiClient.post<unknown>("/finance/budget-plans", body);
      const plan = budgetPlanSchema.parse(saved);
      if (payload.activate && !payload.planId) {
        // created with activate already
      } else if (payload.activate) {
        await apiClient.post(`/finance/budget-plans/${plan.id}/activate`);
      }
      setSuccess("Saved");
      setReloadKey((key) => key + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save budget");
    } finally {
      setSaving(false);
    }
  }

  async function activate(planId: number) {
    setSaving(true);
    setError(null);
    try {
      await apiClient.post(`/finance/budget-plans/${planId}/activate`);
      setSuccess("Active budget updated");
      setReloadKey((key) => key + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to activate budget");
    } finally {
      setSaving(false);
    }
  }

  async function deactivate(planId: number) {
    setSaving(true);
    setError(null);
    try {
      await apiClient.post(`/finance/budget-plans/${planId}/deactivate`);
      setSuccess("No budget is active");
      setReloadKey((key) => key + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to deactivate budget");
    } finally {
      setSaving(false);
    }
  }

  async function duplicate(planId: number) {
    setSaving(true);
    setError(null);
    try {
      await apiClient.post(`/finance/budget-plans/${planId}/duplicate`, {});
      setSuccess("Budget duplicated");
      setReloadKey((key) => key + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to duplicate budget");
    } finally {
      setSaving(false);
    }
  }

  async function reset(planId: number) {
    setSaving(true);
    setError(null);
    try {
      await apiClient.post(`/finance/budget-plans/${planId}/reset`);
      setSuccess("Reset to suggested figures");
      setReloadKey((key) => key + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reset budget");
    } finally {
      setSaving(false);
    }
  }

  async function refresh(planId: number) {
    setSaving(true);
    setError(null);
    try {
      await apiClient.post(`/finance/budget-plans/${planId}/refresh`);
      setSuccess("Suggested figures refreshed. Your overrides were kept.");
      setReloadKey((key) => key + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh budget");
    } finally {
      setSaving(false);
    }
  }

  async function remove(planId: number) {
    setSaving(true);
    setError(null);
    try {
      await apiClient.delete(`/finance/budget-plans/${planId}`);
      setSuccess("Budget removed");
      setReloadKey((key) => key + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete budget");
    } finally {
      setSaving(false);
    }
  }

  async function loadPlan(planId: number): Promise<BudgetPlanItem[] | null> {
    try {
      const data = await apiClient.get<unknown>(`/finance/budget-plans/${planId}`);
      return budgetPlanSchema.parse(data).items;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open budget");
      return null;
    }
  }

  if (authLoading || !user) return <AuthLoadingShell />;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Budget"
        description="A monthly plan derived from your recorded income, commitments, debts, and tax reserves — not a forecast and not a list of actual transactions."
      />
      {error ? (
        <div className="mt-4">
          <ErrorBanner message={error} />
        </div>
      ) : null}
      {success ? (
        <div className="mt-4">
          <SuccessBanner message={success} />
        </div>
      ) : null}
      {loading || !suggestions ? (
        <div className="mt-6">
          <PageLoading label="Analysing financial records for budget suggestions" rows={3} />
        </div>
      ) : (
        <div className="mt-6">
          <BudgetPlanView
            key={`${reloadKey}-${initialPlan?.id ?? "new"}`}
            suggestions={suggestions}
            initialPlan={
              initialPlan
                ? {
                    id: initialPlan.id,
                    name: initialPlan.name,
                    strategy: initialPlan.strategy,
                    items: initialPlan.items,
                  }
                : null
            }
            canWrite={canWrite(user)}
            saving={saving}
            onSave={save}
            onActivate={activate}
            onDeactivate={deactivate}
            onDuplicate={duplicate}
            onReset={reset}
            onRefresh={refresh}
            onDelete={remove}
            onLoadPlan={loadPlan}
          />
        </div>
      )}
    </AppShell>
  );
}
