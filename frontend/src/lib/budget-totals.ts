import type { BudgetPlanLine, BudgetTotals } from "@/lib/finance-schemas";

const DEBT_MIN = new Set(["Debt minimum payments", "Loan repayments"]);
const DEBT_OVER = new Set(["Debt overpayments", "Debt overpayment"]);
const BUFFER = new Set(["Emergency buffer", "Business buffer", "Savings"]);
const DISCRETIONARY = new Set(["Personal spending", "Subscriptions", "Other"]);
const TAX = new Set(["Tax reserve", "VAT reserve", "Corporation tax reserve"]);

export function summariseBudgetLines(
  lines: Array<Pick<BudgetPlanLine, "category" | "amount_gbp">>,
  incomeGbp: number,
): BudgetTotals {
  let total = 0;
  let debtPay = 0;
  let overpay = 0;
  let buffer = 0;
  let discretionary = 0;
  let tax = 0;
  for (const line of lines) {
    const amount = Number(line.amount_gbp) || 0;
    total += amount;
    if (DEBT_MIN.has(line.category)) debtPay += amount;
    else if (DEBT_OVER.has(line.category)) {
      overpay += amount;
      debtPay += amount;
    } else if (BUFFER.has(line.category)) buffer += amount;
    else if (DISCRETIONARY.has(line.category)) discretionary += amount;
    else if (TAX.has(line.category)) tax += amount;
  }
  const surplus = round2(incomeGbp - total);
  return {
    income_gbp: round2(incomeGbp),
    committed_gbp: round2(total - discretionary - overpay - buffer),
    total_spending_gbp: round2(total),
    debt_payment_gbp: round2(debtPay),
    debt_overpayment_gbp: round2(overpay),
    buffer_gbp: round2(buffer),
    discretionary_gbp: round2(discretionary),
    tax_reserve_gbp: round2(tax),
    surplus_gbp: surplus,
    shortfall_gbp: round2(Math.abs(Math.min(surplus, 0))),
  };
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}
