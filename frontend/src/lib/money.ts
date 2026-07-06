export type MoneyTone = "positive" | "negative" | "neutral";

/** How a finance figure should be signed in the UI. */
export type FinanceAmountRole =
  | "asset"
  | "debt"
  | "inflow"
  | "outflow"
  | "signed";

export type FinanceAmountFormat = {
  text: string;
  tone: MoneyTone;
  className: string;
  role: FinanceAmountRole;
};

const FINANCE_POSITIVE_CLASS = "text-emerald-600 dark:text-emerald-400";
const FINANCE_NEGATIVE_CLASS = "text-red-600 dark:text-red-400";
const FINANCE_NEUTRAL_CLASS = "text-[var(--foreground)]";

export const FINANCE_SIGN_LEGEND =
  "Green + figures are assets or money in (credit). Red − figures are debts or money out (debit).";

/** Format a GBP amount with an explicit +/− sign for finance dashboards. */
export function formatFinanceGbp(
  value: number | null | undefined,
  role: FinanceAmountRole,
): FinanceAmountFormat {
  if (value == null || Number.isNaN(value)) {
    return {
      text: "—",
      tone: "neutral",
      className: FINANCE_NEUTRAL_CLASS,
      role,
    };
  }

  const absText = formatGbp(Math.abs(value));

  switch (role) {
    case "asset":
    case "inflow":
      return {
        text: `+${absText}`,
        tone: "positive",
        className: FINANCE_POSITIVE_CLASS,
        role,
      };
    case "debt":
    case "outflow":
      return {
        text: `−${absText}`,
        tone: "negative",
        className: FINANCE_NEGATIVE_CLASS,
        role,
      };
    case "signed":
      if (value >= 0) {
        return {
          text: `+${absText}`,
          tone: "positive",
          className: FINANCE_POSITIVE_CLASS,
          role,
        };
      }
      return {
        text: `−${absText}`,
        tone: "negative",
        className: FINANCE_NEGATIVE_CLASS,
        role,
      };
    default:
      return {
        text: absText,
        tone: "neutral",
        className: FINANCE_NEUTRAL_CLASS,
        role,
      };
  }
}

/** Pick asset vs debt display for a bank/account balance. */
export function financeRoleForAccountBalance(
  accountType: string,
  balanceGbp: number,
): FinanceAmountRole {
  const debtTypes = new Set([
    "credit_card",
    "loan",
    "mortgage",
    "directors_loan",
    "capital_on_tap",
    "creditors",
  ]);
  if (debtTypes.has(accountType)) {
    return "debt";
  }
  if (accountType === "current" && balanceGbp < 0) {
    return "signed";
  }
  return "asset";
}

/** Cash-flow entry amounts are stored signed; infer display role from type. */
export function financeRoleForCashflowEntry(
  entryType: string,
  amountGbp: number,
): FinanceAmountRole {
  if (amountGbp < 0) {
    return "outflow";
  }
  if (amountGbp > 0) {
    return "inflow";
  }
  if (entryType === "income") {
    return "inflow";
  }
  return "outflow";
}

export function financeRoleForDebtType(debtType: string): FinanceAmountRole {
  return debtType === "mortgage" ? "debt" : "debt";
}

export function currencySymbol(currency: string): string {
  if (currency === "GBP") return "£";
  if (currency === "EUR") return "€";
  return "$";
}

export function formatCurrencyAmount(value: number, currency: string): string {
  return `${currencySymbol(currency)}${Math.abs(value).toFixed(2)}`;
}

export function formatGbp(value: number | null | undefined, decimals = 2): string {
  if (value == null || Number.isNaN(value)) {
    return "—";
  }
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

/** Plain accounting currency — no +/- colours (matches QuickFile report figures). */
export function formatAccountingGbp(value: number | null | undefined, decimals = 2): string {
  if (value == null || Number.isNaN(value)) {
    return "—";
  }
  if (value < 0) {
    return `(${formatGbp(Math.abs(value), decimals)})`;
  }
  return formatGbp(value, decimals);
}

export function formatQuickFilePeriod(fromDate: string, toDate: string): string {
  const format = (iso: string) => {
    const [year, month, day] = iso.split("-").map(Number);
    const date = new Date(year, month - 1, day);
    return date.toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  };
  return `${format(fromDate)} to ${format(toDate)}`;
}

export function formatPercent(value: number | null | undefined, decimals = 1): string {
  if (value == null || Number.isNaN(value)) {
    return "—";
  }
  return `${value.toFixed(decimals)}%`;
}

export function formatMonthLabel(month: string): string {
  const [year, mon] = month.split("-");
  const date = new Date(Number(year), Number(mon) - 1, 1);
  return date.toLocaleDateString("en-GB", { month: "long", year: "numeric" });
}

export function currentMonthKey(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export type SavingsFormat = {
  amount: string;
  headline: string;
  sublabel: string;
  tone: MoneyTone;
  className: string;
};

/** Format savings vs a no-solar bill — positive = saved, negative = costlier than no-solar. */
export function formatSavings(value: number, currency: string): SavingsFormat {
  const amount = formatCurrencyAmount(value, currency);
  if (value > 0.005) {
    return {
      amount,
      headline: `${amount} saved`,
      sublabel: "vs no solar",
      tone: "positive",
      className: "text-emerald-600 dark:text-emerald-400",
    };
  }
  if (value < -0.005) {
    return {
      amount,
      headline: `${amount} more than no-solar`,
      sublabel: "import-heavy window",
      tone: "negative",
      className: "text-amber-600 dark:text-amber-400",
    };
  }
  return {
    amount,
    headline: "Break-even vs no solar",
    sublabel: "same as a no-solar bill",
    tone: "neutral",
    className: "text-[var(--foreground)]",
  };
}

export type CompareDeltaFormat = {
  text: string;
  tone: "up" | "down" | "neutral";
};

export function formatCompareDelta(
  current: number,
  previous: number,
  unit: string,
  higherIsBetter: boolean,
  periodLabel: string,
): CompareDeltaFormat {
  const diff = current - previous;
  if (Math.abs(diff) < 0.01) {
    return { text: `No change vs ${periodLabel}`, tone: "neutral" };
  }
  const improved = higherIsBetter ? diff > 0 : diff < 0;
  const sign = diff > 0 ? "+" : "−";
  const formatted =
    unit === "GBP" || unit === "£"
      ? `${sign}${formatCurrencyAmount(diff, "GBP")}`
      : `${sign}${Math.abs(diff).toFixed(1)}${unit === "%" ? "%" : ` ${unit}`}`;
  return {
    text: `${formatted} vs ${periodLabel}`,
    tone: improved ? "up" : "down",
  };
}

export function formatMetricValue(value: number, unit: string, currency = "GBP"): string {
  if (unit === "GBP" || unit === "£") {
    const savings = formatSavings(value, currency);
    return savings.amount;
  }
  if (unit === "%") {
    return `${value.toFixed(1)}%`;
  }
  return `${value.toFixed(1)} ${unit}`;
}

export const SAVINGS_EXPLAINER =
  "Savings = your bill vs a no-solar bill at the import rate. A negative value means an import-heavy window (e.g. battery or EV charging).";

export type CompareRange = "day" | "week" | "month";

export function compareRangeLabels(range: CompareRange): {
  title: string;
  subtitle: string;
  previousLabel: string;
} {
  if (range === "week") {
    return {
      title: "This week vs last week",
      subtitle: "Rolling 7 days compared to the prior 7 days",
      previousLabel: "last week",
    };
  }
  if (range === "month") {
    return {
      title: "This month vs last month",
      subtitle: "Rolling 30 days compared to the prior 30 days",
      previousLabel: "last month",
    };
  }
  return {
    title: "Today vs yesterday",
    subtitle: "Rolling 24h compared to the prior 24h",
    previousLabel: "yesterday",
  };
}
