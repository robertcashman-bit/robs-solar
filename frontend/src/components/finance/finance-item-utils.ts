import type { FinanceItem } from "@/components/finance/FinanceItemList";

export function isNonZero(value: number | null | undefined): boolean {
  return value != null && !Number.isNaN(value) && Math.abs(value) >= 0.005;
}

/** Zero-balance accounts that should still appear (e.g. MBNA credit card to configure). */
export function keepZeroBalanceAccount(account: {
  name: string;
  account_type: string;
}): boolean {
  const name = account.name.toLowerCase();
  return name.includes("mbna") && account.account_type === "credit_card";
}

export function showAccountWithBalance(account: {
  name: string;
  account_type: string;
  balance_gbp: number;
}): boolean {
  return isNonZero(account.balance_gbp) || keepZeroBalanceAccount(account);
}

export function filterZeroFinanceItems(items: FinanceItem[], dualColumn = false): FinanceItem[] {
  return items.filter((item) => {
    if (dualColumn) {
      return isNonZero(item.monthAmount) || isNonZero(item.ytdAmount);
    }
    return isNonZero(item.amount);
  });
}

export function sumItems(items: FinanceItem[]): number {
  return items.reduce((total, item) => total + (item.amount ?? 0), 0);
}
