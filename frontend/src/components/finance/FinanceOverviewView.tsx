"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { FinanceDataGapsBanner } from "@/components/finance/FinanceDataGapsBanner";
import { formatGbp } from "@/lib/money";
import type {
  FinanceOverview,
  OverviewSideBreakdown,
  PeriodFlowSummary,
} from "@/lib/finance-schemas";

type FinanceOverviewViewProps = {
  overview: FinanceOverview;
  onDismissInsight?: (id: number) => void;
};

type Line = OverviewSideBreakdown["owned"][number];

function primaryLines(lines: Line[], limit = 5): Line[] {
  return lines.filter((line) => line.tier !== "more").slice(0, limit);
}

function moreLines(lines: Line[]): Line[] {
  return lines.filter((line) => line.tier === "more");
}

function LineList({
  lines,
  empty,
}: {
  lines: Line[];
  empty?: string;
}) {
  if (lines.length === 0) {
    return empty ? <p className="mt-2 text-sm text-[var(--muted)]">{empty}</p> : null;
  }
  return (
    <ul className="mt-2 space-y-1.5">
      {lines.map((line) => (
        <li
          key={line.key}
          className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 text-sm"
        >
          <span className="text-[var(--muted)]">{line.label}</span>
          <span className="font-semibold tabular-nums tracking-tight">
            {line.kind === "gap" && line.amount_gbp == null ? "—" : formatGbp(line.amount_gbp)}
          </span>
          {line.hint ? (
            <span className="basis-full text-[0.7rem] leading-snug text-[var(--muted)]">
              {line.hint}
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function PeriodMoneyRow({
  title,
  flow,
}: {
  title: string;
  flow: PeriodFlowSummary | null | undefined;
}) {
  if (!flow) return null;
  const hasData =
    flow.transaction_count > 0
    || flow.income_gbp !== 0
    || flow.spending_gbp !== 0
    || flow.source === "quickfile_pnl";
  const inLabel = flow.money_in_label || "Money in";
  const outLabel = flow.money_out_label || "Money out";
  const periodHint = flow.coverage_note || flow.label;

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">{title}</p>
      {periodHint ? (
        <p className="mt-0.5 text-xs text-[var(--muted)]">{periodHint}</p>
      ) : null}
      <div className="mt-3 grid grid-cols-2 gap-3">
        <div>
          <p className="text-xs text-[var(--muted)]">{inLabel}</p>
          <p className="mt-0.5 text-lg font-bold tabular-nums">
            {hasData ? formatGbp(flow.income_gbp) : "—"}
          </p>
        </div>
        <div>
          <p className="text-xs text-[var(--muted)]">{outLabel}</p>
          <p className="mt-0.5 text-lg font-bold tabular-nums">
            {hasData ? formatGbp(flow.spending_gbp) : "—"}
          </p>
        </div>
      </div>
    </div>
  );
}

function SideColumn({
  title,
  breakdown,
}: {
  title: string;
  breakdown: OverviewSideBreakdown | null | undefined;
}) {
  const [open, setOpen] = useState(false);
  const ownedPrimary = useMemo(
    () => primaryLines(breakdown?.owned ?? []),
    [breakdown],
  );
  const owedPrimary = useMemo(
    () => primaryLines(breakdown?.owed ?? []),
    [breakdown],
  );
  const ownedMore = useMemo(() => moreLines(breakdown?.owned ?? []), [breakdown]);
  const owedMore = useMemo(() => moreLines(breakdown?.owed ?? []), [breakdown]);
  const hasMore = ownedMore.length > 0 || owedMore.length > 0;
  const left = breakdown?.whats_left_gbp ?? 0;

  return (
    <section
      className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5"
      aria-label={title}
      role="region"
    >
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>

      <div className="mt-4 space-y-5">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            What you own
          </p>
          <p className="mt-1 text-2xl font-bold tabular-nums tracking-tight">
            {formatGbp(breakdown?.owned_total_gbp)}
          </p>
          <LineList lines={ownedPrimary} empty="Nothing recorded yet" />
        </div>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            What you owe
          </p>
          <p className="mt-1 text-2xl font-bold tabular-nums tracking-tight">
            {formatGbp(breakdown?.owed_total_gbp)}
          </p>
          <LineList lines={owedPrimary} empty="Nothing recorded yet" />
        </div>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            What&apos;s left
          </p>
          <p
            className={`mt-1 text-2xl font-bold tabular-nums tracking-tight ${
              left < 0 ? "text-amber-800 dark:text-amber-200" : ""
            }`}
          >
            {formatGbp(left)}
          </p>
        </div>
      </div>

      {hasMore ? (
        <div className="mt-4 border-t border-[var(--border)] pt-3">
          <button
            type="button"
            className="text-sm font-medium underline underline-offset-2"
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
          >
            {open ? "Hide more" : "More"}
          </button>
          {open ? (
            <div className="mt-3 space-y-4">
              {ownedMore.length > 0 ? (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                    Also owned
                  </p>
                  <LineList lines={ownedMore} />
                </div>
              ) : null}
              {owedMore.length > 0 ? (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                    Also owed
                  </p>
                  <LineList lines={owedMore} />
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function fallbackPersonalBreakdown(overview: FinanceOverview): OverviewSideBreakdown {
  return {
    side: "personal",
    owned_total_gbp: round2(
      (overview.personal_bank_balance_gbp ?? 0)
        + (overview.personal_overdraft_gbp ?? 0)
        + (overview.property_gbp ?? 0)
        + (overview.pension_configured === false ? 0 : overview.pension_value_gbp ?? 0)
        + (overview.company_owes_director_gbp ?? 0),
    ),
    owed_total_gbp: round2(
      (overview.total_personal_debt_gbp ?? 0)
        + (overview.personal_overdraft_gbp ?? 0)
        + (overview.director_owes_company_gbp ?? 0),
    ),
    whats_left_gbp: overview.personal_net_worth_gbp ?? 0,
    owned: [
      {
        key: "personal_bank",
        label: "Bank",
        amount_gbp: round2(
          (overview.personal_bank_balance_gbp ?? 0) + (overview.personal_overdraft_gbp ?? 0),
        ),
        kind: "asset",
        tier: "primary",
        hint: "",
      },
      {
        key: "house_share",
        label: "House share",
        amount_gbp: overview.property_gbp ?? 0,
        kind: "asset",
        tier: "primary",
        hint: "Your half only",
      },
      {
        key: "pension",
        label: "Pension",
        amount_gbp: overview.pension_configured === false ? null : overview.pension_value_gbp,
        kind: "asset",
        tier: "primary",
        hint: "",
      },
    ],
    owed: [
      {
        key: "mortgage",
        label: "House mortgage",
        amount_gbp: overview.mortgage_balance_gbp,
        kind: "debt",
        tier: "primary",
        hint: "Your half of the joint mortgage",
      },
    ],
  };
}

function fallbackBusinessBreakdown(overview: FinanceOverview): OverviewSideBreakdown {
  return {
    side: "business",
    owned_total_gbp: round2(
      (overview.business_bank_balance_gbp ?? 0)
        + (overview.business_overdraft_gbp ?? 0)
        + (overview.debtors_gbp ?? 0)
        + (overview.vat_reserve_gbp ?? 0)
        + (overview.corp_tax_reserve_gbp ?? 0)
        + (overview.director_owes_company_gbp ?? 0),
    ),
    owed_total_gbp: round2(
      (overview.total_business_debt_gbp ?? 0)
        + (overview.business_overdraft_gbp ?? 0)
        + (overview.company_owes_director_gbp ?? 0),
    ),
    whats_left_gbp: overview.company_position_gbp ?? 0,
    owned: [
      {
        key: "business_bank",
        label: "Bank",
        amount_gbp: round2(
          (overview.business_bank_balance_gbp ?? 0) + (overview.business_overdraft_gbp ?? 0),
        ),
        kind: "asset",
        tier: "primary",
        hint: "",
      },
    ],
    owed: [],
  };
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

export function FinanceOverviewView({ overview }: FinanceOverviewViewProps) {
  const personal = overview.personal_breakdown ?? fallbackPersonalBreakdown(overview);
  const business = overview.business_breakdown ?? fallbackBusinessBreakdown(overview);
  const combined = overview.net_worth_estimate_gbp;

  return (
    <div className="space-y-8">
      <section aria-label="What's left" role="region" className="text-center sm:text-left">
        <p className="text-sm font-medium text-[var(--muted)]">What&apos;s left</p>
        <p
          className={`mt-1 text-4xl font-bold tracking-tight tabular-nums sm:text-5xl ${
            combined < 0 ? "text-amber-800 dark:text-amber-200" : ""
          }`}
        >
          {formatGbp(combined)}
        </p>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <SideColumn title="You" breakdown={personal} />
        <SideColumn title="Defence Legal" breakdown={business} />
      </div>

      <section aria-label="Money this period" className="space-y-3">
        <h2 className="text-sm font-semibold">Money this period</h2>
        <div className="grid gap-3 lg:grid-cols-2">
          <PeriodMoneyRow title="You" flow={overview.personal_period_flow} />
          <PeriodMoneyRow title="Defence Legal" flow={overview.business_period_flow} />
        </div>
      </section>

      <FinanceDataGapsBanner gaps={overview.data_gaps} />

      <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
        <h2 className="font-semibold">Quick links</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {[
            ["/finance/personal", "You"],
            ["/finance/business", "Defence Legal"],
            ["/finance/debts", "Debts"],
            ["/finance/cash-flow", "Cash flow"],
            ["/finance/budget", "Budget"],
            ["/finance/reports", "Reports"],
            ["/finance/connect", "Connect banks"],
          ].map(([href, label]) => (
            <Link key={href} href={href} className="solar-btn-ghost text-sm">
              {label}
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
