import type { FinanceItem } from "@/components/finance/FinanceItemList";
import type {
  QuickFileProfitAndLossSummary,
  QuickFileReportSection,
  QuickFileReports,
} from "@/lib/finance-schemas";
import type { FinanceAmountRole } from "@/lib/money";

import { filterZeroFinanceItems } from "./finance-item-utils";

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

function plLineRole(sectionKey: string): FinanceAmountRole {
  if (sectionKey === "Turnover") return "inflow";
  if (sectionKey === "LessCostofSales" || sectionKey === "LessExpenses") return "outflow";
  return "signed";
}

function plSubtotalRole(sectionKey: string): FinanceAmountRole {
  if (sectionKey === "Turnover") return "inflow";
  if (sectionKey === "LessCostofSales" || sectionKey === "LessExpenses") return "outflow";
  return "signed";
}

function bsLineRole(sectionKey: string): FinanceAmountRole {
  if (sectionKey === "FixedAssets" || sectionKey === "CurrentAssets") return "asset";
  if (sectionKey === "CurrentLiabilities" || sectionKey === "LongTermLiabilities") return "debt";
  return "signed";
}

function findMatchingLine(
  section: QuickFileReportSection | undefined,
  nominalCode: string | null | undefined,
  label: string,
) {
  if (!section) return undefined;
  return section.lines.find(
    (line) =>
      (nominalCode && line.nominal_code === nominalCode) ||
      line.label === label,
  );
}

function dualColumnAmounts(
  monthAmount: number | null | undefined,
  monthRole: FinanceAmountRole,
  ytdAmount: number | null | undefined,
  ytdRole: FinanceAmountRole,
  dualColumn: boolean,
): Pick<FinanceItem, "amount" | "role" | "monthAmount" | "monthRole" | "ytdAmount" | "ytdRole"> {
  if (dualColumn) {
    return {
      monthAmount,
      monthRole,
      ytdAmount,
      ytdRole,
    };
  }
  return {
    amount: monthAmount,
    role: monthRole,
  };
}

function buildProfitAndLossFromSections(
  month: QuickFileProfitAndLossSummary,
  ytd: QuickFileProfitAndLossSummary | null | undefined,
): FinanceItem[] {
  const dualColumn = Boolean(ytd?.sections?.length);
  const ytdByKey = new Map((ytd?.sections ?? []).map((section) => [section.key, section]));
  const items: FinanceItem[] = [];

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
        const role = plLineRole(section.key);
        items.push({
          key: lineKey(section.key, line.nominal_code ?? line.label),
          label: line.label,
          nominalCode: line.nominal_code,
          indent: true,
          ...dualColumnAmounts(line.amount_gbp, role, ytdLine?.amount_gbp, role, dualColumn),
        });
      }

      if (section.subtotal_gbp != null) {
        const role = plSubtotalRole(section.key);
        items.push({
          key: lineKey(section.key, "subtotal"),
          label: section.label,
          total: true,
          ...dualColumnAmounts(
            section.subtotal_gbp,
            role,
            ytdSection?.subtotal_gbp,
            role,
            dualColumn,
          ),
        });
      }
      continue;
    }

    if (section.subtotal_gbp == null) continue;

    const role = "signed";
    items.push({
      key: lineKey(section.key, "total"),
      label: section.subtotal_label ?? section.label,
      total: section.is_total || section.key === "GrossProfit",
      ...dualColumnAmounts(
        section.subtotal_gbp,
        role,
        ytdSection?.subtotal_gbp,
        role,
        dualColumn,
      ),
    });
  }

  return items;
}

function buildBalanceSheetFromSections(bs: NonNullable<QuickFileReports["balance_sheet"]>): FinanceItem[] {
  const items: FinanceItem[] = [];

  for (const section of bs.sections) {
    if (section.lines.length > 0) {
      items.push({
        key: lineKey(section.key, "header"),
        label: section.label,
        sectionHeader: true,
      });

      for (const line of section.lines) {
        const role = bsLineRole(section.key);
        items.push({
          key: lineKey(section.key, line.nominal_code ?? line.label),
          label: line.label,
          nominalCode: line.nominal_code,
          indent: true,
          amount: line.amount_gbp,
          role,
        });
      }
    }

    if (section.subtotal_gbp != null) {
      const role = bsLineRole(section.key);
      items.push({
        key: lineKey(section.key, "subtotal"),
        label: section.label,
        amount: section.subtotal_gbp,
        role,
        total: true,
      });
    }
  }

  return items;
}

function buildSummaryProfitAndLossItems(
  month: QuickFileProfitAndLossSummary | null | undefined,
  ytd: QuickFileProfitAndLossSummary | null | undefined,
): FinanceItem[] {
  const dualColumn = Boolean(month && ytd);

  return [
    {
      key: "turnover",
      label: "Turnover",
      amount: month?.turnover_gbp,
      role: "inflow",
      monthAmount: month?.turnover_gbp,
      monthRole: "inflow",
      ytdAmount: ytd?.turnover_gbp,
      ytdRole: "inflow",
    },
    {
      key: "cost-of-sales",
      label: "Less: Cost of sales",
      amount: month?.cost_of_sales_gbp,
      role: "outflow",
      monthAmount: month?.cost_of_sales_gbp,
      monthRole: "outflow",
      ytdAmount: ytd?.cost_of_sales_gbp,
      ytdRole: "outflow",
    },
    {
      key: "gross-profit",
      label: "Gross profit",
      amount: month ? grossProfit(month) : undefined,
      role: "signed",
      monthAmount: month ? grossProfit(month) : undefined,
      monthRole: "signed",
      ytdAmount: ytd ? grossProfit(ytd) : undefined,
      ytdRole: "signed",
    },
    {
      key: "operating-expenses",
      label: "Less: Expenses",
      amount: month ? operatingExpenses(month) : undefined,
      role: "outflow",
      monthAmount: month ? operatingExpenses(month) : undefined,
      monthRole: "outflow",
      ytdAmount: ytd ? operatingExpenses(ytd) : undefined,
      ytdRole: "outflow",
    },
    {
      key: "net-profit",
      label: "Net profit",
      amount: month?.net_profit_gbp,
      role: "signed",
      monthAmount: month?.net_profit_gbp,
      monthRole: "signed",
      ytdAmount: ytd?.net_profit_gbp,
      ytdRole: "signed",
      total: true,
    },
  ];
}

function buildSummaryBalanceSheetItems(bs: NonNullable<QuickFileReports["balance_sheet"]>): FinanceItem[] {
  return [
    {
      key: "fixed-assets",
      label: "Fixed assets",
      amount: bs.fixed_assets_gbp,
      role: "asset",
    },
    {
      key: "current-assets",
      label: "Current assets",
      amount: bs.current_assets_gbp,
      role: "asset",
    },
    {
      key: "debtors",
      label: "Debtors control",
      amount: bs.debtors_gbp,
      role: "asset",
    },
    {
      key: "current-liabilities",
      label: "Creditors: amounts falling due within one year",
      amount: bs.current_liabilities_gbp,
      role: "debt",
    },
    {
      key: "creditors",
      label: "Creditors control",
      amount: bs.creditors_gbp,
      role: "debt",
    },
    {
      key: "vat-liability",
      label: "VAT liability",
      amount: bs.vat_liability_gbp,
      role: "debt",
    },
    {
      key: "long-term-liabilities",
      label: "Creditors: amounts falling due after one year",
      amount: bs.long_term_liabilities_gbp,
      role: "debt",
    },
    {
      key: "capital-reserves",
      label: "Capital and reserves",
      amount: bs.capital_and_reserves_gbp,
      role: "signed",
      total: true,
    },
  ];
}

export function buildQuickFileProfitAndLossItems(reports: QuickFileReports): {
  items: FinanceItem[];
  subtitle: string;
  dualColumn: boolean;
  fullBreakdown: boolean;
} {
  const month = reports.profit_and_loss_month;
  const ytd = reports.profit_and_loss_ytd;
  const dualColumn = Boolean(month && ytd);
  const fullBreakdown = Boolean(month?.sections?.length);

  const items = fullBreakdown && month
    ? buildProfitAndLossFromSections(month, ytd)
    : buildSummaryProfitAndLossItems(month, ytd);

  const subtitle = month && ytd
    ? `Month: ${plPeriodLabel(month)} · YTD: ${plPeriodLabel(ytd)}`
    : month
      ? plPeriodLabel(month)
      : ytd
        ? plPeriodLabel(ytd)
        : "";

  return {
    items: fullBreakdown ? items : filterZeroFinanceItems(items, dualColumn),
    subtitle,
    dualColumn,
    fullBreakdown,
  };
}

export function buildQuickFileBalanceSheetItems(reports: QuickFileReports): {
  items: FinanceItem[];
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
    items: fullBreakdown ? items : filterZeroFinanceItems(items),
    subtitle: `As at ${bs.to_date}`,
    fullBreakdown,
  };
}

export function hasQuickFileStatements(reports: QuickFileReports | null | undefined): boolean {
  if (!reports) return false;
  return Boolean(
    reports.profit_and_loss_month ||
      reports.profit_and_loss_ytd ||
      reports.balance_sheet,
  );
}
