import type { FinanceItem } from "@/components/finance/FinanceItemList";
import type { FinanceAccount } from "@/lib/finance-schemas";
import { financeRoleForAccountBalance } from "@/lib/money";

import { filterZeroFinanceItems, isNonZero, keepZeroBalanceAccount, sumItems } from "./finance-item-utils";

type BusinessAccountBucket = "current_assets" | "short_term_debt" | "long_term_debt";

const BUCKET_LABELS: Record<BusinessAccountBucket, string> = {
  current_assets: "Current assets",
  short_term_debt: "Short-term debt",
  long_term_debt: "Long-term debt",
};

const BUCKET_ORDER: BusinessAccountBucket[] = [
  "current_assets",
  "short_term_debt",
  "long_term_debt",
];

function categorizeBusinessAccount(account: FinanceAccount): BusinessAccountBucket {
  switch (account.account_type) {
    case "credit_card":
    case "capital_on_tap":
    case "creditors":
      return "short_term_debt";
    case "directors_loan":
    case "loan":
      return "long_term_debt";
    case "current":
      return account.balance_gbp < 0 ? "short_term_debt" : "current_assets";
    case "debtors":
    case "vat_reserve":
    case "corp_tax_reserve":
    case "pension":
    default:
      return "current_assets";
  }
}

function accountDisplayAmount(account: FinanceAccount): number {
  const role = financeRoleForAccountBalance(account.account_type, account.balance_gbp);
  if (role === "debt" || role === "outflow" || (account.account_type === "current" && account.balance_gbp < 0)) {
    return Math.abs(account.balance_gbp);
  }
  return account.balance_gbp;
}

function accountToItem(account: FinanceAccount): FinanceItem {
  const amount = accountDisplayAmount(account);
  const role =
    account.account_type === "current" && account.balance_gbp < 0
      ? "debt"
      : financeRoleForAccountBalance(account.account_type, account.balance_gbp);

  return {
    key: `account-${account.id}`,
    label: account.name,
    amount,
    role,
    historic: account.is_historic,
  };
}

export type BusinessAccountSection = {
  bucket: BusinessAccountBucket;
  title: string;
  items: FinanceItem[];
  subtotal: number;
};

export function buildBusinessAccountSections(accounts: FinanceAccount[]): BusinessAccountSection[] {
  const buckets: Record<BusinessAccountBucket, FinanceItem[]> = {
    current_assets: [],
    short_term_debt: [],
    long_term_debt: [],
  };

  for (const account of accounts) {
    if (account.scope !== "business") continue;
    const item = accountToItem(account);
    if (!isNonZero(item.amount) && !keepZeroBalanceAccount(account)) continue;
    buckets[categorizeBusinessAccount(account)].push(item);
  }

  return BUCKET_ORDER.map((bucket) => {
    const items = filterZeroFinanceItems(
      buckets[bucket].sort((a, b) => a.label.localeCompare(b.label)),
    );
    return {
      bucket,
      title: BUCKET_LABELS[bucket],
      items,
      subtotal: sumItems(items),
    };
  }).filter((section) => section.items.length > 0);
}
