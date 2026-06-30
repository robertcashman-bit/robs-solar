export type MoneyTone = "positive" | "negative" | "neutral";

export function currencySymbol(currency: string): string {
  if (currency === "GBP") return "£";
  if (currency === "EUR") return "€";
  return "$";
}

export function formatCurrencyAmount(value: number, currency: string): string {
  return `${currencySymbol(currency)}${Math.abs(value).toFixed(2)}`;
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
