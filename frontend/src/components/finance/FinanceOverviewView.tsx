import Link from "next/link";

import { InsightCard } from "@/components/finance/InsightCard";
import { MetricTile } from "@/components/finance/MetricTile";
import type { FinanceOverview } from "@/lib/finance-schemas";

type FinanceOverviewViewProps = {
  overview: FinanceOverview;
};

export function FinanceOverviewView({ overview }: FinanceOverviewViewProps) {
  return (
    <div className="space-y-8">
      <section>
        <h2 className="solar-section-title">Balances</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricTile label="Personal bank" value={overview.personal_bank_balance_gbp} />
          <MetricTile label="Business bank" value={overview.business_bank_balance_gbp} />
          <MetricTile
            label="Cash after bills"
            value={overview.cash_after_bills_gbp}
            positive={overview.cash_after_bills_gbp > 0}
            warning={overview.cash_after_bills_gbp < 500}
          />
          <MetricTile
            label="Net worth (estimate)"
            value={overview.net_worth_estimate_gbp}
            positive={overview.net_worth_estimate_gbp > 0}
          />
        </div>
      </section>

      <section>
        <h2 className="solar-section-title">Monthly flow</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <MetricTile label="Monthly income" value={overview.monthly_income_gbp} positive />
          <MetricTile label="Monthly spending" value={overview.monthly_spending_gbp} />
          <MetricTile
            label="Monthly surplus"
            value={overview.monthly_surplus_gbp}
            positive={overview.monthly_surplus_gbp >= 0}
            warning={overview.monthly_surplus_gbp < 0}
          />
        </div>
      </section>

      <section>
        <h2 className="solar-section-title">Debts &amp; reserves</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricTile label="Personal debt" value={overview.total_personal_debt_gbp} warning />
          <MetricTile label="Business debt" value={overview.total_business_debt_gbp} warning />
          <MetricTile label="Credit cards" value={overview.credit_card_balances_gbp} warning />
          <MetricTile label="Loans" value={overview.loan_balances_gbp} />
          <MetricTile label="Mortgage" value={overview.mortgage_balance_gbp} />
          <MetricTile label="Pension" value={overview.pension_value_gbp} positive />
          <MetricTile label="Director's loan" value={overview.directors_loan_gbp} />
          <MetricTile
            label="VAT reserve"
            value={overview.vat_reserve_gbp}
            warning={overview.vat_reserve_warning}
            hint={overview.vat_reserve_warning ? "VAT reserve appears low" : undefined}
          />
          <MetricTile
            label="Corp tax reserve"
            value={overview.corp_tax_reserve_gbp}
            warning={overview.corp_tax_reserve_warning}
          />
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between gap-3">
          <h2 className="solar-section-title">Alerts &amp; recommendations</h2>
          <Link href="/finance/reports" className="solar-btn-ghost text-sm">
            View reports
          </Link>
        </div>
        {overview.insights.length === 0 ? (
          <p className="mt-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-6 text-sm text-[var(--muted)]">
            No active insights. Add accounts and snapshots on the Personal, Business, or Debts pages.
          </p>
        ) : (
          <div className="mt-4 grid gap-3">
            {overview.insights.map((insight) => (
              <InsightCard key={insight.id} insight={insight} />
            ))}
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
        <h2 className="font-semibold">Quick links</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {[
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
        <p className="mt-3 text-xs text-[var(--muted)]">
          Live solar savings and inverter data are in the{" "}
          <Link href="/energy" className="underline">
            Energy / Solar
          </Link>{" "}
          section.
        </p>
      </section>
    </div>
  );
}
