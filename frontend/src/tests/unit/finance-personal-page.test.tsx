import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import PersonalFinancePage from "@/app/(finance)/finance/personal/page";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { username: "admin", role: "admin" },
    loading: false,
    authResolved: true,
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/finance/personal",
}));

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: vi.fn(async (path: string) => {
      if (path === "/finance/accounts?scope=personal") {
        return [
          {
            id: 1,
            scope: "personal",
            account_type: "current",
            name: "Current",
            provider: "",
            balance_gbp: 13.12,
            notes: "",
            source: "manual",
            is_active: true,
            created_at: "2010-01-01T00:00:00Z",
            updated_at: "2010-01-01T00:00:00Z",
          },
          {
            id: 2,
            scope: "personal",
            account_type: "pension",
            name: "Pension",
            provider: "",
            balance_gbp: 57726.94,
            notes: "",
            source: "manual",
            is_active: true,
            created_at: "2010-01-01T00:00:00Z",
            updated_at: "2010-01-01T00:00:00Z",
          },
          {
            id: 3,
            scope: "personal",
            account_type: "property",
            name: "House",
            provider: "",
            balance_gbp: 350000,
            notes: "",
            source: "manual",
            is_active: true,
            created_at: "2010-01-01T00:00:00Z",
            updated_at: "2010-01-01T00:00:00Z",
          },
        ];
      }
      if (path.startsWith("/finance/liabilities")) {
        return [
          {
            id: 14,
            scope: "personal",
            name: "House mortgage",
            debt_type: "mortgage",
            balance_gbp: 82210.5,
            interest_rate_pct: 4,
            minimum_payment_gbp: 900,
            overpayment_gbp: 0,
            original_balance_gbp: null,
            payment_day: null,
            credit_limit_gbp: null,
            account_id: null,
            notes: "",
            source: "manual",
            is_active: true,
            interest_rate_known: true,
            dla_direction: null,
            created_at: "2010-01-01T00:00:00Z",
            updated_at: "2010-01-01T00:00:00Z",
          },
          {
            id: 15,
            scope: "personal",
            name: "Director loan",
            debt_type: "directors_loan",
            balance_gbp: 10287.1,
            interest_rate_pct: 0,
            minimum_payment_gbp: 0,
            overpayment_gbp: 0,
            original_balance_gbp: null,
            payment_day: null,
            credit_limit_gbp: null,
            account_id: null,
            notes: "",
            source: "manual",
            is_active: true,
            interest_rate_known: true,
            dla_direction: "director_owes_company",
            created_at: "2010-01-01T00:00:00Z",
            updated_at: "2010-01-01T00:00:00Z",
          },
        ];
      }
      if (path.startsWith("/finance/overview")) {
        return {
          personal_bank_balance_gbp: 13.12,
          business_bank_balance_gbp: 0,
          total_personal_debt_gbp: 82210.5,
          total_business_debt_gbp: 0,
          monthly_income_gbp: 0,
          monthly_spending_gbp: 0,
          cash_after_bills_gbp: 13.12,
          vat_reserve_gbp: 0,
          corp_tax_reserve_gbp: 0,
          vat_reserve_warning: false,
          corp_tax_reserve_warning: false,
          credit_card_balances_gbp: 0,
          personal_credit_card_balances_gbp: 0,
          loan_balances_gbp: 0,
          personal_loan_balances_gbp: 0,
          mortgage_balance_gbp: 82210.5,
          pension_value_gbp: 57726.94,
          directors_loan_gbp: 10287.1,
          net_worth_estimate_gbp: 280864.71,
          monthly_surplus_gbp: 0,
          personal_overdraft_gbp: 0,
          property_gbp: 350000,
          personal_net_worth_gbp: 280864.71,
          company_position_gbp: 0,
          director_owes_company_gbp: 10287.1,
          company_owes_director_gbp: 0,
          external_debt_gbp: 82210.5,
          total_debt_gbp: 92497.6,
          cash_available_gbp: 13.12,
          insights: [],
        };
      }
      if (path.startsWith("/finance/period-flow")) {
        return {
          period: "1m",
          scope: "personal",
          label: "Last month",
          date_from: "2026-07-01",
          date_to: "2026-07-31",
          months_requested: 1,
          months_with_data: 0,
          transaction_count: 0,
          income_gbp: 0,
          spending_gbp: 0,
          surplus_gbp: 0,
          history_partial: true,
          coverage_note: "No stored transactions in last month.",
        };
      }
      if (path.startsWith("/finance/pnl-compare")) {
        return { scope: "personal", as_of: "2026-08-18", rows: [] };
      }
      if (path.startsWith("/finance/budgets/active")) {
        return null;
      }
      if (path === "/finance/snapshots/personal") {
        return [
          {
            id: 4,
            snapshot_date: "2010-01-01",
            monthly_income_gbp: 9999,
            monthly_spending_gbp: 100,
            household_bills_gbp: 50,
            debt_repayments_gbp: 10,
            surplus_deficit_gbp: 9889,
            notes: "",
            created_at: "2010-01-01T00:00:00Z",
          },
        ];
      }
      return [];
    }),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

function tile(label: string) {
  const heading = screen.getAllByText(label).find((node) => node.tagName === "P");
  const card = heading?.closest("div");
  if (!card) {
    throw new Error(`No tile for ${label}`);
  }
  return within(card);
}

describe("PersonalFinancePage", () => {
  it("does not show an older snapshot as this month's income or surplus", async () => {
    render(<PersonalFinancePage />);
    expect(await screen.findByText("£407,740.06")).toBeInTheDocument();
    expect(tile("Personal monthly income").getByText("—")).toBeInTheDocument();
    expect(tile("Personal monthly surplus").getByText("—")).toBeInTheDocument();
    expect(screen.queryByText("£9,999.00")).not.toBeInTheDocument();
    expect(screen.queryByText("£9,889.00")).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText("Income")).toHaveValue("");
    expect(screen.getByText("Personal house (your half)")).toBeInTheDocument();
    expect(screen.getByText("Your half of £700,000. Other half ignored.")).toBeInTheDocument();
    expect(screen.getByText("Of which house mortgage")).toBeInTheDocument();
    const mortgageRow = screen.getByText("Of which house mortgage").closest("li");
    expect(mortgageRow).toHaveTextContent("£82,210.50");
    expect(screen.getByText(/From the personal mortgage liability/)).toBeInTheDocument();
    expect(tile("Personal assets").getByText("£407,740.06")).toBeInTheDocument();
    expect(tile("Personal debts").getByText("£82,210.50")).toBeInTheDocument();
    expect(tile("Personal bank").getByText("£13.12")).toBeInTheDocument();
    expect(tile("Personal pension").getByText("£57,726.94")).toBeInTheDocument();
    expect(screen.getByText("Director's loan payable")).toBeInTheDocument();
    expect(screen.queryByText("Director's loan receivable")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Income, spend & surplus" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "This month to date" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "This month to date" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("keeps Position tiles when period-flow fails", async () => {
    const { apiClient } = await import("@/lib/api-client");
    const get = apiClient.get as ReturnType<typeof vi.fn>;
    get.mockImplementation(async (path: string) => {
      if (path.startsWith("/finance/period-flow")) {
        throw new Error("The server took too long to respond.");
      }
      if (path.startsWith("/finance/overview")) {
        return {
          personal_bank_balance_gbp: -2503.91,
          business_bank_balance_gbp: -1948.6,
          total_personal_debt_gbp: 134645.42,
          total_business_debt_gbp: 32064.7,
          monthly_income_gbp: 0,
          monthly_spending_gbp: 0,
          cash_after_bills_gbp: -2503.91,
          vat_reserve_gbp: 0.47,
          corp_tax_reserve_gbp: 0,
          vat_reserve_warning: false,
          corp_tax_reserve_warning: false,
          credit_card_balances_gbp: 0,
          personal_credit_card_balances_gbp: 0,
          loan_balances_gbp: 0,
          personal_loan_balances_gbp: 0,
          mortgage_balance_gbp: 82210.5,
          pension_value_gbp: 57726.94,
          directors_loan_gbp: 10287.1,
          net_worth_estimate_gbp: 242463.23,
          monthly_surplus_gbp: 0,
          personal_overdraft_gbp: 2517.14,
          property_gbp: 350000,
          personal_net_worth_gbp: 280864.71,
          company_position_gbp: -36058.58,
          director_owes_company_gbp: 0,
          company_owes_director_gbp: 10287.1,
          external_debt_gbp: 166710.12,
          total_debt_gbp: 176997.22,
          cash_available_gbp: -4452.51,
          insights: [],
        };
      }
      if (path === "/finance/accounts?scope=personal") return [];
      if (path.startsWith("/finance/liabilities")) return [];
      if (path.startsWith("/finance/pnl-compare")) {
        return { scope: "personal", as_of: "2026-08-19", rows: [] };
      }
      if (path.startsWith("/finance/budgets/active")) return null;
      if (path === "/finance/snapshots/personal") return [];
      return [];
    });

    render(<PersonalFinancePage />);
    expect(await screen.findByText("£350,000.00")).toBeInTheDocument();
    expect(tile("Personal pension").getByText("£57,726.94")).toBeInTheDocument();
    expect(tile("Personal debts").getByText("£134,645.42")).toBeInTheDocument();
    expect(tile("Personal bank").getByText("-£2,503.91")).toBeInTheDocument();
    expect(screen.getByText("Director's loan receivable")).toBeInTheDocument();
  });

  it("keeps Position tiles when overview fails", async () => {
    const { apiClient } = await import("@/lib/api-client");
    const get = apiClient.get as ReturnType<typeof vi.fn>;
    get.mockImplementation(async (path: string) => {
      if (path.startsWith("/finance/overview")) {
        throw new Error("The server took too long to respond.");
      }
      if (path === "/finance/accounts?scope=personal") {
        return [
          {
            id: 1,
            scope: "personal",
            account_type: "current",
            name: "Current",
            provider: "",
            balance_gbp: 100,
            notes: "",
            source: "manual",
            is_active: true,
            created_at: "2010-01-01T00:00:00Z",
            updated_at: "2010-01-01T00:00:00Z",
          },
          {
            id: 2,
            scope: "personal",
            account_type: "pension",
            name: "Pension",
            provider: "",
            balance_gbp: 50000,
            notes: "",
            source: "manual",
            is_active: true,
            created_at: "2010-01-01T00:00:00Z",
            updated_at: "2010-01-01T00:00:00Z",
          },
          {
            id: 3,
            scope: "personal",
            account_type: "property",
            name: "House",
            provider: "",
            balance_gbp: 350000,
            notes: "",
            source: "manual",
            is_active: true,
            created_at: "2010-01-01T00:00:00Z",
            updated_at: "2010-01-01T00:00:00Z",
          },
        ];
      }
      if (path.startsWith("/finance/liabilities")) {
        return [
          {
            id: 14,
            scope: "personal",
            name: "House mortgage",
            debt_type: "mortgage",
            balance_gbp: 80000,
            interest_rate_pct: 4,
            minimum_payment_gbp: 900,
            overpayment_gbp: 0,
            original_balance_gbp: null,
            payment_day: null,
            credit_limit_gbp: null,
            account_id: null,
            notes: "",
            source: "manual",
            is_active: true,
            interest_rate_known: true,
            dla_direction: null,
            created_at: "2010-01-01T00:00:00Z",
            updated_at: "2010-01-01T00:00:00Z",
          },
        ];
      }
      if (path.startsWith("/finance/period-flow")) {
        return {
          period: "mtd",
          scope: "personal",
          label: "This month to date",
          date_from: "2026-08-01",
          date_to: "2026-08-19",
          months_requested: 1,
          months_with_data: 0,
          transaction_count: 0,
          income_gbp: 0,
          spending_gbp: 0,
          surplus_gbp: 0,
          history_partial: true,
          coverage_note: "No stored transactions.",
        };
      }
      if (path.startsWith("/finance/pnl-compare")) {
        return { scope: "personal", as_of: "2026-08-19", rows: [] };
      }
      if (path.startsWith("/finance/budgets/active")) return null;
      if (path === "/finance/snapshots/personal") return [];
      return [];
    });

    render(<PersonalFinancePage />);
    expect(await screen.findByText("Personal house (your half)")).toBeInTheDocument();
    expect(tile("Personal house (your half)").getByText("£350,000.00")).toBeInTheDocument();
    expect(tile("Personal bank").getByText("£100.00")).toBeInTheDocument();
    expect(tile("Personal pension").getByText("£50,000.00")).toBeInTheDocument();
    expect(tile("Personal debts").getByText("£80,000.00")).toBeInTheDocument();
  });
});
