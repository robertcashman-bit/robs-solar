import type { FinanceItem } from "@/components/finance/FinanceItemList";
import type { FinanceAccount, FinanceLiability } from "@/lib/finance-schemas";
import { financeRoleForAccountBalance, financeRoleForDebtType } from "@/lib/money";

import { filterZeroFinanceItems, isNonZero } from "./finance-item-utils";

function accountDisplayAmount(account: FinanceAccount): number {
  const role = financeRoleForAccountBalance(account.account_type, account.balance_gbp);
  if (role === "debt" || role === "outflow") {
    return Math.abs(account.balance_gbp);
  }
  return account.balance_gbp;
}

export function buildAccountItems(
  accounts: FinanceAccount[],
  scope?: FinanceAccount["scope"],
): FinanceItem[] {
  const items = [...accounts]
    .filter((account) => (scope ? account.scope === scope : true))
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((account) => ({
      key: `account-${account.id}`,
      label: account.name,
      amount: accountDisplayAmount(account),
      role: financeRoleForAccountBalance(account.account_type, account.balance_gbp),
      historic: account.is_historic,
    }))
    .filter((item) => isNonZero(item.amount));

  return filterZeroFinanceItems(items);
}

export function buildLiabilityItems(
  liabilities: FinanceLiability[],
  scope?: FinanceLiability["scope"],
): FinanceItem[] {
  const items = [...liabilities]
    .filter((liability) => (scope ? liability.scope === scope : true))
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((liability) => ({
      key: `liability-${liability.id}`,
      label: liability.name,
      amount: Math.abs(liability.balance_gbp),
      role: financeRoleForDebtType(liability.debt_type),
      historic: liability.is_historic,
    }))
    .filter((item) => isNonZero(item.amount));

  return filterZeroFinanceItems(items);
}
