import Link from "next/link";

import type { FinanceAccount, FinanceLiability, FinanceOverview } from "@/lib/finance-schemas";
import { formatGbp } from "@/lib/money";

type AccountStatementsProps = {
  overview?: Pick<FinanceOverview, "property_gbp" | "mortgage_balance_gbp"> | null;
  accounts: FinanceAccount[];
  liabilities: FinanceLiability[];
};

function isSandboxAccount(account: FinanceAccount): boolean {
  const provider = (account.provider || "").trim().toLowerCase();
  const name = account.name.trim().toLowerCase();
  if (name.includes("mock aspsp") || provider.includes("mock aspsp")) {
    return true;
  }
  return account.source === "open_banking" && provider.includes("sandbox");
}

function keepZeroBalance(account: FinanceAccount): boolean {
  return account.name.toLowerCase().includes("mbna") && account.account_type === "credit_card";
}

function visibleAccounts(accounts: FinanceAccount[]): FinanceAccount[] {
  return accounts.filter((account) => {
    if (!account.is_active || isSandboxAccount(account)) {
      return false;
    }
    return Math.abs(account.balance_gbp) >= 0.005 || keepZeroBalance(account);
  });
}

export function AccountStatements({ overview, accounts, liabilities }: AccountStatementsProps) {
  const propertyMissing =
    overview != null && overview.property_gbp <= 0 && overview.mortgage_balance_gbp > 0;
  const shownAccounts = visibleAccounts(accounts);
  const shownDebts = liabilities.filter(
    (item) => item.is_active && Math.abs(item.balance_gbp) >= 0.005,
  );

  if (!propertyMissing && shownAccounts.length === 0 && shownDebts.length === 0) {
    return null;
  }

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

      {shownAccounts.length > 0 ? (
        <section>
          <h3 className="text-sm font-semibold">Accounts</h3>
          <p className="mt-1 text-xs text-[var(--muted)]">
            One line per account. Zero balances and sandbox accounts are hidden.
          </p>
          <ul className="mt-3 space-y-2">
            {shownAccounts.map((account) => (
              <li
                key={account.id}
                className="flex items-center justify-between rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm"
              >
                <span>
                  {account.name}
                  <span className="ml-2 text-[var(--muted)]">
                    {account.scope} · {account.account_type.replaceAll("_", " ")}
                  </span>
                </span>
                <span className="font-semibold tabular-nums">{formatGbp(account.balance_gbp)}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {shownDebts.length > 0 ? (
        <section>
          <h3 className="text-sm font-semibold">Debts</h3>
          <p className="mt-1 text-xs text-[var(--muted)]">One line per active liability.</p>
          <ul className="mt-3 space-y-2">
            {shownDebts.map((debt) => (
              <li
                key={debt.id}
                className="flex items-center justify-between rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm"
              >
                <span>
                  {debt.name}
                  <span className="ml-2 text-[var(--muted)]">
                    {debt.scope} · {debt.debt_type.replaceAll("_", " ")}
                    {debt.interest_rate_known === false ? " · APR unknown" : ""}
                  </span>
                </span>
                <span className="font-semibold tabular-nums">{formatGbp(debt.balance_gbp)}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
