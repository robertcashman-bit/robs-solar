import { describe, expect, it } from "vitest";

import {
  buildQuickFileBalanceSheetItems,
  buildQuickFileProfitAndLossItems,
} from "@/components/finance/quickfile-statement-rows";
import type { QuickFileReports } from "@/lib/finance-schemas";

const fullReports: QuickFileReports = {
  synced_at: "2026-01-15T10:00:00Z",
  profit_and_loss_month: {
    from_date: "2026-01-01",
    to_date: "2026-01-31",
    turnover_gbp: 50000,
    cost_of_sales_gbp: 12000,
    expenses_gbp: 30000,
    net_profit_gbp: 20000,
    sections: [
      {
        key: "Turnover",
        label: "Turnover",
        lines: [
          { nominal_code: "4000", label: "Sales", amount_gbp: 45000 },
          { nominal_code: "4001", label: "Other income", amount_gbp: 5000 },
        ],
        subtotal_gbp: 50000,
      },
      {
        key: "LessCostofSales",
        label: "Less: Cost of sales",
        lines: [{ nominal_code: "5000", label: "Purchases", amount_gbp: 12000 }],
        subtotal_gbp: 12000,
      },
      {
        key: "GrossProfit",
        label: "Gross profit",
        lines: [],
        subtotal_gbp: 38000,
        subtotal_label: "Gross profit",
      },
      {
        key: "LessExpenses",
        label: "Less: Expenses",
        lines: [{ nominal_code: "7000", label: "Rent", amount_gbp: 18000 }],
        subtotal_gbp: 18000,
      },
      {
        key: "NetProfit",
        label: "Net profit",
        lines: [],
        subtotal_gbp: 20000,
        subtotal_label: "Net profit",
        is_total: true,
      },
    ],
  },
  profit_and_loss_ytd: {
    from_date: "2026-01-01",
    to_date: "2026-01-31",
    turnover_gbp: 120000,
    cost_of_sales_gbp: 24000,
    expenses_gbp: 72000,
    net_profit_gbp: 48000,
    sections: [
      {
        key: "Turnover",
        label: "Turnover",
        lines: [{ nominal_code: "4000", label: "Sales", amount_gbp: 120000 }],
        subtotal_gbp: 120000,
      },
      {
        key: "LessCostofSales",
        label: "Less: Cost of sales",
        lines: [{ nominal_code: "5000", label: "Purchases", amount_gbp: 24000 }],
        subtotal_gbp: 24000,
      },
      {
        key: "GrossProfit",
        label: "Gross profit",
        lines: [],
        subtotal_gbp: 96000,
        subtotal_label: "Gross profit",
      },
      {
        key: "LessExpenses",
        label: "Less: Expenses",
        lines: [{ nominal_code: "7000", label: "Rent", amount_gbp: 48000 }],
        subtotal_gbp: 48000,
      },
      {
        key: "NetProfit",
        label: "Net profit",
        lines: [],
        subtotal_gbp: 48000,
        subtotal_label: "Net profit",
        is_total: true,
      },
    ],
  },
  balance_sheet: {
    to_date: "2026-01-31",
    fixed_assets_gbp: 15000,
    current_assets_gbp: 25000,
    current_liabilities_gbp: 8000,
    long_term_liabilities_gbp: 12000,
    capital_and_reserves_gbp: 20000,
    debtors_gbp: 8883,
    creditors_gbp: 5000,
    vat_liability_gbp: 3000,
    sections: [
      {
        key: "FixedAssets",
        label: "Fixed assets",
        lines: [{ nominal_code: "1000", label: "Plant and machinery", amount_gbp: 15000 }],
        subtotal_gbp: 15000,
      },
      {
        key: "CurrentAssets",
        label: "Current assets",
        lines: [
          { nominal_code: "1200", label: "Debtors control account", amount_gbp: 8883 },
          { nominal_code: "1201", label: "Bank current account", amount_gbp: 16117 },
        ],
        subtotal_gbp: 25000,
      },
      {
        key: "CurrentLiabilities",
        label: "Creditors: amounts falling due within one year",
        lines: [
          { nominal_code: "2200", label: "Creditors control account", amount_gbp: 5000 },
          { nominal_code: "2201", label: "VAT liability", amount_gbp: 3000 },
        ],
        subtotal_gbp: 8000,
      },
      {
        key: "LongTermLiabilities",
        label: "Creditors: amounts falling due after one year",
        lines: [{ nominal_code: "2300", label: "Bank loan", amount_gbp: 12000 }],
        subtotal_gbp: 12000,
      },
      {
        key: "CapitalAndReserves",
        label: "Capital and reserves",
        lines: [{ nominal_code: "3000", label: "Share capital", amount_gbp: 20000 }],
        subtotal_gbp: 20000,
        is_total: true,
      },
    ],
  },
};

describe("quickfile-statement-rows", () => {
  it("renders every nominal line for full P&L breakdown", () => {
    const { items, fullBreakdown, dualColumn } = buildQuickFileProfitAndLossItems(fullReports);

    expect(fullBreakdown).toBe(true);
    expect(dualColumn).toBe(true);
    expect(items.some((item) => item.label === "Sales" && item.indent)).toBe(true);
    expect(items.some((item) => item.label === "Other income" && item.indent)).toBe(true);
    expect(items.some((item) => item.label === "Purchases" && item.indent)).toBe(true);
    expect(items.some((item) => item.label === "Rent" && item.monthAmount === 18000)).toBe(true);
    expect(items.some((item) => item.label === "Rent" && item.ytdAmount === 48000)).toBe(true);
    expect(items.some((item) => item.label === "Gross profit" && item.total)).toBe(true);
    expect(items.some((item) => item.label === "Net profit" && item.total)).toBe(true);
  });

  it("renders every nominal line for full balance sheet breakdown", () => {
    const { items, fullBreakdown } = buildQuickFileBalanceSheetItems(fullReports);

    expect(fullBreakdown).toBe(true);
    expect(items.some((item) => item.label === "Plant and machinery")).toBe(true);
    expect(items.some((item) => item.label === "Debtors control account")).toBe(true);
    expect(items.some((item) => item.label === "VAT liability")).toBe(true);
    expect(items.some((item) => item.label === "Bank loan")).toBe(true);
    expect(items.filter((item) => item.sectionHeader).length).toBeGreaterThanOrEqual(5);
  });

  it("keeps zero lines when full breakdown is present", () => {
    const reports: QuickFileReports = {
      ...fullReports,
      profit_and_loss_month: {
        ...fullReports.profit_and_loss_month!,
        sections: [
          {
            key: "Turnover",
            label: "Turnover",
            lines: [{ nominal_code: "4000", label: "Sales", amount_gbp: 0 }],
            subtotal_gbp: 0,
          },
          {
            key: "LessCostofSales",
            label: "Less: Cost of sales",
            lines: [],
            subtotal_gbp: 0,
          },
          {
            key: "GrossProfit",
            label: "Gross profit",
            lines: [],
            subtotal_gbp: 0,
            subtotal_label: "Gross profit",
          },
          {
            key: "LessExpenses",
            label: "Less: Expenses",
            lines: [],
            subtotal_gbp: 0,
          },
          {
            key: "NetProfit",
            label: "Net profit",
            lines: [],
            subtotal_gbp: 0,
            subtotal_label: "Net profit",
            is_total: true,
          },
        ],
      },
      profit_and_loss_ytd: null,
    };

    const { items, fullBreakdown } = buildQuickFileProfitAndLossItems(reports);
    expect(fullBreakdown).toBe(true);
    expect(items.some((item) => item.label === "Sales" && item.amount === 0)).toBe(true);
  });
});
