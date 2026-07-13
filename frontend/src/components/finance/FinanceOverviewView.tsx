import Link from "next/link";

import { buildAccountItems, buildLiabilityItems } from "@/components/finance/account-item-list";
import { FinanceItemList } from "@/components/finance/FinanceItemList";
import { FinanceSignLegend } from "@/components/finance/FinanceSignLegend";
import type { FinanceAccount, FinanceLiability, FinanceOverview } from "@/lib/finance-schemas";
import { formatFinanceGbp } from "@/lib/money";

type FinanceOverviewViewProps = {
  overview: FinanceOverview;
  accounts?: FinanceAccount[];
  liabilities?: FinanceLiability[];
};

function PanelSummary({
  rows,
}: {
  rows: { label: string; value: number; role: "asset" | "debt" | "signed" }[];
}) {
  return (
    <dl className="grid grid-cols-2 gap-3">
      {rows.map((row) => {
        const amount = formatFinanceGbp(row.value, row.role);
        return (
          <div
            key={row.label}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface-sunken)]/40 px-3 py-2"
          >
            <dt className="text-xs uppercase tracking-wide text-[var(--muted)]">{row.label}</dt>
            <dd className={`mt-1 text-lg font-semibold tabular-nums ${amount.className}`}>
              {amount.text}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

export function FinanceOverviewView({
  overview,
  accounts = [],
  liabilities = [],
}: FinanceOverviewViewProps) {
  const personalAccounts = accounts.filter((a) => a.scope === "personal");
  const personalLiabilities = liabilities.filter((l) => l.scope === "personal");
  const businessAccounts = accounts.filter((a) => a.scope === "business");
  const businessLiabilities = liabilities.filter((l) => l.scope === "business");

  const personalAccountItems = buildAccountItems(personalAccounts, "personal");
  const personalDebtItems = buildLiabilityItems(personalLiabilities, "personal");
  const businessAccountItems = buildAccountItems(businessAccounts, "business");
  const businessDebtItems = buildLiabilityItems(businessLiabilities, "business");

  const personalDebt = Math.abs(overview.total_personal_debt_gbp);
  const businessDebt = Math.abs(overview.total_business_debt_gbp);

  return (
    <div className="space-y-6">
      <FinanceSignLegend />

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Personal panel */}
        <section
          aria-label="Personal finances"
          className="space-y-4 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5"
        >
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">Personal</h2>
              <p className="mt-0.5 text-sm text-[var(--muted)]">Your household money</p>
            </div>
            <Link href="/finance/personal" className="solar-btn-ghost text-sm">
              Open
            </Link>
          </div>

          <PanelSummary
            rows={[
              { label: "Bank balance", value: overview.personal_bank_balance_gbp, role: "signed" },
              { label: "Debts", value: personalDebt, role: "debt" },
              { label: "Property", value: overview.property_value_gbp, role: "asset" },
              { label: "Pension", value: overview.pension_value_gbp, role: "asset" },
            ]}
          />

          {personalAccountItems.length > 0 ? (
            <FinanceItemList
              title="Accounts"
              subtitle="One line per account — zero balances hidden"
              items={personalAccountItems}
            />
          ) : (
            <p className="rounded-xl border border-[var(--border)] px-4 py-3 text-sm text-[var(--muted)]">
              No personal accounts yet.{" "}
              <Link href="/finance/connect" className="underline">
                Connect a bank
              </Link>{" "}
              or{" "}
              <Link href="/finance/personal" className="underline">
                add one manually
              </Link>
              .
            </p>
          )}

          {personalDebtItems.length > 0 ? (
            <FinanceItemList
              title="Debts"
              subtitle="Credit cards, loans, and mortgage"
              items={personalDebtItems}
            />
          ) : null}
        </section>

        {/* Business panel */}
        <section
          aria-label="Business finances"
          className="space-y-4 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5"
        >
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">Business</h2>
              <p className="mt-0.5 text-sm text-[var(--muted)]">
                {overview.business_income_from_quickfile
                  ? "Live from QuickFile"
                  : "Manual snapshot"}
              </p>
            </div>
            <Link href="/finance/business" className="solar-btn-ghost text-sm">
              Open
            </Link>
          </div>

          <PanelSummary
            rows={[
              {
                label: "Net profit (month)",
                value: overview.business_monthly_net_profit_gbp,
                role: "signed",
              },
              { label: "Bank balance", value: overview.business_bank_balance_gbp, role: "signed" },
              { label: "Debtors owed", value: overview.debtors_gbp, role: "asset" },
              { label: "Debts", value: businessDebt, role: "debt" },
            ]}
          />

          {overview.business_income_from_quickfile ? (
            <FinanceItemList
              title="Profit & loss (this month)"
              items={[
                {
                  key: "turnover",
                  label: "Turnover",
                  amount: overview.business_monthly_turnover_gbp,
                  role: "inflow",
                },
                {
                  key: "expenses",
                  label: "Expenses",
                  amount: overview.business_monthly_expenses_gbp,
                  role: "outflow",
                },
                {
                  key: "net-profit",
                  label: "Net profit",
                  amount: overview.business_monthly_net_profit_gbp,
                  role: "signed",
                  total: true,
                },
              ]}
            />
          ) : null}

          {businessAccountItems.length > 0 ? (
            <FinanceItemList
              title="Accounts & loans"
              subtitle="Live balances from QuickFile — zero balances hidden"
              items={businessAccountItems}
            />
          ) : (
            <p className="rounded-xl border border-[var(--border)] px-4 py-3 text-sm text-[var(--muted)]">
              No business accounts yet.{" "}
              <Link href="/finance/connect" className="underline">
                Sync QuickFile
              </Link>
              .
            </p>
          )}

          {businessDebtItems.length > 0 ? (
            <FinanceItemList
              title="Business debts"
              items={businessDebtItems}
            />
          ) : null}
        </section>
      </div>

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
            ["/finance/reports", "Reports"],
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
