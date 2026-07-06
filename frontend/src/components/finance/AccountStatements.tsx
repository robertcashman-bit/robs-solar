import Link from "next/link";

import { buildAccountItems, buildLiabilityItems } from "@/components/finance/account-item-list";
import { FinanceAmount } from "@/components/finance/FinanceAmount";
import { FinanceItemList } from "@/components/finance/FinanceItemList";
import { filterZeroFinanceItems } from "@/components/finance/finance-item-utils";
import type { FinanceAccount, FinanceLiability, FinanceOverview } from "@/lib/finance-schemas";
import { formatFinanceGbp, formatGbp } from "@/lib/money";

type AccountStatementsProps = {
  overview: FinanceOverview;
  accounts: FinanceAccount[];
  liabilities?: FinanceLiability[];
  showMonthly?: boolean;
  scope?: FinanceAccount["scope"];
};

function isHistoric(overview: FinanceOverview, field: string) {
  return overview.historic_fields.includes(field);
}

export function AccountStatements({
  overview,
  accounts,
  liabilities = [],
  showMonthly = true,
  scope = "personal",
}: AccountStatementsProps) {
  const propertyMissing = overview.property_value_gbp <= 0 && overview.mortgage_balance_gbp > 0;
  const accountItems = buildAccountItems(accounts, scope);
  const liabilityItems = buildLiabilityItems(liabilities, scope);
  const totalDebt = Math.abs(overview.total_debt_gbp);

  const assets = formatFinanceGbp(overview.total_assets_gbp, "asset");
  const debtDisplay = formatGbp(totalDebt);
  const net = formatFinanceGbp(overview.net_worth_estimate_gbp, "signed");

  return (
    <div className="space-y-6">
      {propertyMissing ? (
        <p className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-100">
          Property value is not set but a mortgage is recorded — net worth will look too low until
          you add the house value on the{" "}
          <Link href="/finance/personal" className="underline">
            Personal
          </Link>{" "}
          page (account type: Property).
        </p>
      ) : null}

      {accountItems.length > 0 ? (
        <FinanceItemList
          title="Personal accounts"
          subtitle="Each account on its own line — zero balances hidden"
          items={accountItems}
        />
      ) : null}

      {liabilityItems.length > 0 ? (
        <FinanceItemList
          title="Debts"
          subtitle="Each loan, mortgage, and credit card debt — one line per item"
          items={liabilityItems}
        />
      ) : null}

      <FinanceItemList
        title="Net worth"
        subtitle="Total assets minus total debts"
        items={[
          {
            key: "total-assets",
            label: "Total assets",
            amount: overview.total_assets_gbp,
            role: "asset",
          },
          {
            key: "total-debt",
            label: "Total debts",
            amount: totalDebt,
            role: "debt",
          },
          {
            key: "net-worth",
            label: "Net worth",
            amount: overview.net_worth_estimate_gbp,
            role: "signed",
            total: true,
          },
        ]}
        footer={
          <p className="tabular-nums text-[var(--muted)]">
            <span className={assets.className}>{assets.text}</span> −{" "}
            <span className="text-red-600 dark:text-red-400">{debtDisplay}</span> ={" "}
            <span className={net.className}>{net.text}</span>
            {overview.home_equity_gbp > 0 ? (
              <>
                {" "}
                · home equity{" "}
                <FinanceAmount
                  value={overview.home_equity_gbp}
                  role="signed"
                  className="inline font-medium"
                />
              </>
            ) : null}
          </p>
        }
      />

      {showMonthly ? (
        <FinanceItemList
          title="Personal monthly cash flow"
          subtitle="Typical monthly income and spending"
          items={filterZeroFinanceItems([
            {
              key: "income",
              label: "Income",
              amount: overview.personal_monthly_income_gbp || overview.monthly_income_gbp,
              role: "inflow",
              historic: isHistoric(overview, "personal_monthly_income_gbp"),
            },
            {
              key: "spending",
              label: "Spending",
              amount: overview.monthly_spending_gbp,
              role: "outflow",
              historic: isHistoric(overview, "monthly_spending_gbp"),
            },
            {
              key: "surplus",
              label: "Surplus / (deficit)",
              amount: overview.monthly_surplus_gbp,
              role: "signed",
              historic: isHistoric(overview, "monthly_surplus_gbp"),
              total: true,
            },
          ])}
        />
      ) : null}
    </div>
  );
}
