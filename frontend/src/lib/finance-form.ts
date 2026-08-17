import { parseMoneyInput } from "@/lib/money";

export function requiredMoney(raw: string, label: string): number {
  const value = parseMoneyInput(raw);
  if (value == null) {
    throw new Error(`Enter a valid amount for ${label}.`);
  }
  return value;
}

export function optionalMoney(raw: string): number | null {
  if (!raw.trim()) {
    return null;
  }
  const value = parseMoneyInput(raw);
  if (value == null) {
    throw new Error("Enter a valid amount, or leave the field blank.");
  }
  return value;
}

export function moneyFieldValue(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) {
    return "";
  }
  return String(value);
}

/** Revolving credit accounts that historically stored a limit (AccountsPanel). */
export function accountUsesCreditLimit(accountType: string): boolean {
  return accountType === "credit_card" || accountType === "capital_on_tap";
}

/** Liability types that map to those revolving accounts. */
export function debtUsesCreditLimit(debtType: string): boolean {
  return debtType === "credit_card" || debtType === "business_loan";
}
