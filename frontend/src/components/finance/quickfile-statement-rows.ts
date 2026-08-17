import type {
  QuickFileProfitAndLossSummary,
  QuickFileReportSection,
  QuickFileReports,
} from "@/lib/finance-schemas";

export type QuickFileStatementRow = {
  key: string;
  label: string;
  nominalCode?: string | null;
  indent?: boolean;
  sectionHeader?: boolean;
  total?: boolean;
  amount?: number | null;
  monthAmount?: number | null;
  ytdAmount?: number | null;
};

function grossProfit(pl: QuickFileProfitAndLossSummary) {
  return pl.turnover_gbp - pl.cost_of_sales_gbp;
}

function operatingExpenses(pl: QuickFileProfitAndLossSummary) {
  return pl.expenses_gbp - pl.cost_of_sales_gbp;
}

function plPeriodLabel(pl: QuickFileProfitAndLossSummary) {
  return `${pl.from_date} to ${pl.to_date}`;
}

function lineKey(...parts: string[]) {
  return parts.join("-").toLowerCase().replace(/[^a-z0-9-]+/g, "-");
}

function findMatchingLine(
  section: QuickFileReportSection | undefined,
  nominalCode: string | null | undefined,
  label: string,
) {
  if (!section) return undefined;
  return section.lines.find(
    (line) => (nominalCode && line.nominal_code === nominalCode) || line.label === label,
  );
}

function dualColumnAmounts(
  monthAmount: number | null | undefined,
  ytdAmount: number | null | undefined,
  dualColumn: boolean,
): Pick<QuickFileStatementRow, "amount" | "monthAmount" | "ytdAmount"> {
  if (dualColumn) {
    return { monthAmount, ytdAmount };
  }
  return { amount: monthAmount };
}

function isMeaningfulAmount(value: number | null | undefined) {
  return value != null && Math.abs(value) >= 0.005;
}

function filterZeroRows(items: QuickFileStatementRow[], dualColumn = false): QuickFileStatementRow[] {
  return items.filter((item) => {
    if (item.sectionHeader) return true;
    if (item.total) return true;
    if (dualColumn) {
      return isMeaningfulAmount(item.monthAmount) || isMeaningfulAmount(item.ytdAmount);
    }
    return isMeaningfulAmount(item.amount);
  });
}

function buildProfitAndLossFromSections(
  month: QuickFileProfitAndLossSummary,
  ytd: QuickFileProfitAndLossSummary | null | undefined,
): QuickFileStatementRow[] {
  const dualColumn = Boolean(ytd?.sections?.length);
  const ytdByKey = new Map((ytd?.sections ?? []).map((section) => [section.key, section]));
  const items: QuickFileStatementRow[] = [];

  for (const section of month.sections) {
    const ytdSection = ytdByKey.get(section.key);
    const calculatedOnly = section.lines.length === 0;

    if (!calculatedOnly) {
      items.push({
        key: lineKey(section.key, "header"),
        label: section.label,
        sectionHeader: true,
      });

      for (const line of section.lines) {
        const ytdLine = findMatchingLine(ytdSection, line.nominal_code, line.label);
        items.push({
          key: lineKey(section.key, line.nominal_code ?? line.label),
          label: line.label,
          nominalCode: line.nominal_code,
          indent: true,
          ...dualColumnAmounts(line.amount_gbp, ytdLine?.amount_gbp, dualColumn),
        });
      }

      if (section.subtotal_gbp != null) {
        items.push({
          key: lineKey(section.key, "subtotal"),
          label: section.label,
          total: true,
          ...dualColumnAmounts(section.subtotal_gbp, ytdSection?.subtotal_gbp, dualColumn),
        });
      }
      continue;
    }

    if (section.subtotal_gbp == null) continue;
    items.push({
      key: lineKey(section.key, "total"),
      label: section.subtotal_label ?? section.label,
      total: section.is_total || section.key === "GrossProfit",
      ...dualColumnAmounts(section.subtotal_gbp, ytdSection?.subtotal_gbp, dualColumn),
    });
  }

  return items;
}

function buildBalanceSheetFromSections(
  bs: NonNullable<QuickFileReports["balance_sheet"]>,
): QuickFileStatementRow[] {
  const items: QuickFileStatementRow[] = [];

  for (const section of bs.sections) {
    if (section.lines.length > 0) {
      items.push({
        key: lineKey(section.key, "header"),
        label: section.label,
        sectionHeader: true,
      });

      for (const line of section.lines) {
        items.push({
          key: lineKey(section.key, line.nominal_code ?? line.label),
          label: line.label,
          nominalCode: line.nominal_code,
          indent: true,
          amount: line.amount_gbp,
        });
      }
    }

    if (section.subtotal_gbp != null) {
      items.push({
        key: lineKey(section.key, "subtotal"),
        label: section.label,
        amount: section.subtotal_gbp,
        total: true,
      });
    }
  }

  return items;
}

function buildSummaryProfitAndLossItems(
  month: QuickFileProfitAndLossSummary | null | undefined,
  ytd: QuickFileProfitAndLossSummary | null | undefined,
): QuickFileStatementRow[] {
  return [
    {
      key: "turnover",
      label: "Turnover",
      amount: month?.turnover_gbp,
      monthAmount: month?.turnover_gbp,
      ytdAmount: ytd?.turnover_gbp,
    },
    {
      key: "cost-of-sales",
      label: "Less: Cost of sales",
      amount: month?.cost_of_sales_gbp,
      monthAmount: month?.cost_of_sales_gbp,
      ytdAmount: ytd?.cost_of_sales_gbp,
    },
    {
      key: "gross-profit",
      label: "Gross profit",
      amount: month ? grossProfit(month) : undefined,
      monthAmount: month ? grossProfit(month) : undefined,
      ytdAmount: ytd ? grossProfit(ytd) : undefined,
    },
    {
      key: "operating-expenses",
      label: "Less: Expenses",
      amount: month ? operatingExpenses(month) : undefined,
      monthAmount: month ? operatingExpenses(month) : undefined,
      ytdAmount: ytd ? operatingExpenses(ytd) : undefined,
    },
    {
      key: "net-profit",
      label: "Net profit",
      amount: month?.net_profit_gbp,
      monthAmount: month?.net_profit_gbp,
      ytdAmount: ytd?.net_profit_gbp,
      total: true,
    },
  ];
}

function buildSummaryBalanceSheetItems(
  bs: NonNullable<QuickFileReports["balance_sheet"]>,
): QuickFileStatementRow[] {
  return [
    { key: "fixed-assets", label: "Fixed assets", amount: bs.fixed_assets_gbp },
    { key: "current-assets", label: "Current assets", amount: bs.current_assets_gbp },
    { key: "debtors", label: "Debtors control", amount: bs.debtors_gbp },
    {
      key: "current-liabilities",
      label: "Creditors: amounts falling due within one year",
      amount: bs.current_liabilities_gbp,
    },
    { key: "creditors", label: "Creditors control", amount: bs.creditors_gbp },
    { key: "vat-liability", label: "VAT liability", amount: bs.vat_liability_gbp },
    {
      key: "long-term-liabilities",
      label: "Creditors: amounts falling due after one year",
      amount: bs.long_term_liabilities_gbp,
    },
    {
      key: "capital-reserves",
      label: "Capital and reserves",
      amount: bs.capital_and_reserves_gbp,
      total: true,
    },
  ];
}

export function buildQuickFileProfitAndLossItems(reports: QuickFileReports): {
  items: QuickFileStatementRow[];
  subtitle: string;
  dualColumn: boolean;
  fullBreakdown: boolean;
} {
  const month = reports.profit_and_loss_month;
  const ytd = reports.profit_and_loss_ytd;
  const dualColumn = Boolean(month && ytd);
  const fullBreakdown = Boolean(month?.sections?.length);

  const items =
    fullBreakdown && month
      ? buildProfitAndLossFromSections(month, ytd)
      : buildSummaryProfitAndLossItems(month, ytd);

  const subtitle =
    month && ytd
      ? `Month: ${plPeriodLabel(month)} · YTD: ${plPeriodLabel(ytd)}`
      : month
        ? plPeriodLabel(month)
        : ytd
          ? plPeriodLabel(ytd)
          : "";

  return {
    items: fullBreakdown ? items : filterZeroRows(items, dualColumn),
    subtitle,
    dualColumn,
    fullBreakdown,
  };
}

export function buildQuickFileBalanceSheetItems(reports: QuickFileReports): {
  items: QuickFileStatementRow[];
  subtitle: string;
  fullBreakdown: boolean;
} {
  const bs = reports.balance_sheet;
  if (!bs) {
    return { items: [], subtitle: "", fullBreakdown: false };
  }

  const fullBreakdown = Boolean(bs.sections?.length);
  const items = fullBreakdown
    ? buildBalanceSheetFromSections(bs)
    : buildSummaryBalanceSheetItems(bs);

  return {
    items: fullBreakdown ? items : filterZeroRows(items),
    subtitle: `As at ${bs.to_date}`,
    fullBreakdown,
  };
}

export function hasQuickFileStatements(reports: QuickFileReports | null | undefined): boolean {
  if (!reports) return false;
  return Boolean(
    reports.profit_and_loss_month || reports.profit_and_loss_ytd || reports.balance_sheet,
  );
}
