import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AccountStatements } from "@/components/finance/AccountStatements";
import {
  financeAccountSchema,
  financeLiabilitySchema,
  type FinanceAccount,
  type FinanceLiability,
} from "@/lib/finance-schemas";

function account(overrides: Record<string, unknown> = {}): FinanceAccount {
  return financeAccountSchema.parse({
    id: 1,
    scope: "personal",
    account_type: "current",
    name: "Lloyds",
    provider: "",
    balance_gbp: 1200,
    notes: "",
    source: "manual",
    is_active: true,
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
    ...overrides,
  });
}

function debt(overrides: Record<string, unknown> = {}): FinanceLiability {
  return financeLiabilitySchema.parse({
    id: 1,
    scope: "personal",
    name: "MBNA",
    debt_type: "credit_card",
    balance_gbp: 800,
    interest_rate_pct: 22,
    minimum_payment_gbp: 25,
    overpayment_gbp: 0,
    notes: "",
    is_active: true,
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
    ...overrides,
  });
}

describe("AccountStatements", () => {
  it("warns when a mortgage exists without a property value", () => {
    render(
      <AccountStatements
        overview={{ property_gbp: 0, mortgage_balance_gbp: 150000 }}
        accounts={[]}
        liabilities={[debt({ name: "Mortgage", debt_type: "mortgage", balance_gbp: 150000 })]}
      />,
    );
    expect(screen.getByText(/Property value is not set but a mortgage is recorded/)).toBeInTheDocument();
    expect(screen.getByText("Mortgage")).toBeInTheDocument();
  });

  it("hides sandbox accounts and zero balances except MBNA cards", () => {
    render(
      <AccountStatements
        accounts={[
          account({ id: 1, name: "Lloyds", balance_gbp: 1200 }),
          account({
            id: 2,
            name: "Mock ASPSP Current",
            source: "open_banking",
            provider: "Mock ASPSP",
            balance_gbp: 9999,
          }),
          account({
            id: 3,
            name: "Sandbox Current",
            source: "open_banking",
            provider: "TrueLayer sandbox",
            balance_gbp: 4000,
          }),
          account({ id: 4, name: "Empty saver", account_type: "other", balance_gbp: 0 }),
          account({
            id: 5,
            name: "MBNA",
            account_type: "credit_card",
            balance_gbp: 0,
          }),
        ]}
        liabilities={[]}
      />,
    );
    expect(screen.getByText("Lloyds")).toBeInTheDocument();
    expect(screen.getByText("MBNA")).toBeInTheDocument();
    expect(screen.queryByText("Mock ASPSP Current")).not.toBeInTheDocument();
    expect(screen.queryByText("Sandbox Current")).not.toBeInTheDocument();
    expect(screen.queryByText("Empty saver")).not.toBeInTheDocument();
  });
});
