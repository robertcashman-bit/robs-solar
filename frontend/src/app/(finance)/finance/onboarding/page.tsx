"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { PageHeader } from "@/components/shared/PageHeader";
import { useAuth } from "@/lib/auth-context";

const STEPS = [
  {
    title: "Create or import accounts",
    body: "Add personal and Defence Legal Services Ltd accounts on Personal / Business, or sync from Connect banks.",
    href: "/finance/personal",
  },
  {
    title: "Mark each Personal or Business",
    body: "Every account has a scope. Keep personal and company money separate for accounting.",
    href: "/finance/business",
  },
  {
    title: "Import 6–12 months of transactions",
    body: "Upload CSV/OFX/QIF statements, or sync Lunch Flow / QuickFile / Open Banking.",
    href: "/finance/import",
  },
  {
    title: "Automatic categorisation",
    body: "Imports apply merchant rules. Review anything left uncategorised.",
    href: "/finance/transactions",
  },
  {
    title: "Review low-confidence categories",
    body: "Use the low confidence filter and bulk-correct. Optionally create permanent rules.",
    href: "/finance/transactions",
  },
  {
    title: "Detect recurring transactions",
    body: "Open Budget studio or run recurring detection, then confirm or reject proposals.",
    href: "/finance/budget",
  },
  {
    title: "Configure debts",
    body: "Check credit cards, loans, vehicle finance and minimum payments.",
    href: "/finance/debts",
  },
  {
    title: "Configure tax reserves",
    body: "Set VAT and corporation tax reserve accounts on the business ledger.",
    href: "/finance/business",
  },
  {
    title: "Configure cash buffers",
    body: "Safe to Spend uses personal and business buffers — review on Overview.",
    href: "/",
  },
  {
    title: "Generate first automatic budget",
    body: "Use Generate from history on the Budget page. Recommendations use stored transactions only.",
    href: "/finance/budget",
  },
];

export default function OnboardingPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [step, setStep] = useState(0);

  if (authLoading || !user) {
    if (!authLoading && !user) router.replace("/login");
    return <AuthLoadingShell />;
  }

  const current = STEPS[step];

  return (
    <AppShell>
      <PageHeader
        eyebrow="Setup"
        title="Budgeting onboarding"
        description={`Step ${step + 1} of ${STEPS.length}`}
      />
      <div className="mt-6 max-w-2xl rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-xl font-semibold">{current.title}</h2>
        <p className="mt-2 text-sm text-[var(--muted)]">{current.body}</p>
        <Link
          href={current.href}
          className="mt-4 inline-flex rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white"
        >
          Open this step
        </Link>
        <div className="mt-6 flex gap-2">
          <button
            type="button"
            disabled={step === 0}
            onClick={() => setStep((value) => Math.max(0, value - 1))}
            className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm disabled:opacity-40"
          >
            Back
          </button>
          <button
            type="button"
            disabled={step >= STEPS.length - 1}
            onClick={() => setStep((value) => Math.min(STEPS.length - 1, value + 1))}
            className="rounded-lg bg-teal-700 px-3 py-2 text-sm text-white disabled:opacity-40"
          >
            Next
          </button>
        </div>
        <ol className="mt-8 space-y-2 text-sm text-[var(--muted)]">
          {STEPS.map((item, index) => (
            <li key={item.title} className={index === step ? "font-medium text-[var(--foreground)]" : ""}>
              {index + 1}. {item.title}
            </li>
          ))}
        </ol>
      </div>
    </AppShell>
  );
}
