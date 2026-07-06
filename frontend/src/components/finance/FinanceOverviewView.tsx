import Link from "next/link";

import { AccountStatements } from "@/components/finance/AccountStatements";
import { FinanceSignLegend } from "@/components/finance/FinanceSignLegend";
import type { FinanceAccount, FinanceLiability, FinanceOverview } from "@/lib/finance-schemas";
import { formatFinanceGbp } from "@/lib/money";

type FinanceOverviewViewProps = {
  overview: FinanceOverview;
  accounts?: FinanceAccount[];
  liabilities?: FinanceLiability[];
};

export function FinanceOverviewView({
  overview,
  accounts = [],
  liabilities = [],
}: FinanceOverviewViewProps) {
  const personalAccounts = accounts.filter((a) => a.scope === "personal");
  const personalLiabilities = liabilities.filter((l) => l.scope === "personal");
  const profit = formatFinanceGbp(overview.business_monthly_net_profit_gbp, "signed");

  return (
    <div className="space-y-8">
      <FinanceSignLegend />

      <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="solar-section-title">Business</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Profit &amp; loss and balance sheet live on the Business page.
            </p>
          </div>
          <Link href="/finance/business" className="solar-btn-primary text-sm">
            Open business finance
          </Link>
        </div>
        {overview.business_income_from_quickfile ? (
          <p className="mt-3 text-sm tabular-nums">
            This month net profit:{" "}
            <span className={profit.className}>{profit.text}</span>
          </p>
        ) : null}
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="solar-section-title">Personal accounts &amp; net worth</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Personal bank accounts and debts — one line per item.
          </p>
        </div>
        <AccountStatements
          overview={overview}
          accounts={personalAccounts}
          liabilities={personalLiabilities}
        />
      </section>

      <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
        <h2 className="font-semibold">More pages</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {[
            ["/finance/connect", "Connect banks"],
            ["/finance/personal", "Personal finance"],
            ["/finance/business", "Business finance"],
            ["/finance/debts", "Debts"],
            ["/finance/cash-flow", "Cash flow"],
            ["/finance/budget", "Budget"],
            ["/energy", "Energy / Solar"],
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
