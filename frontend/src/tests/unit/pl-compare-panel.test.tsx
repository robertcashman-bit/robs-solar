import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PlComparePanel } from "@/components/finance/PlComparePanel";

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: vi.fn(async () => ({
      scope: "personal",
      as_of: "2026-08-19",
      rows: [
        {
          key: "6m",
          label: "6 months",
          date_from: "2026-02-19",
          date_to: "2026-08-19",
          income_gbp: 12000,
          spending_gbp: 8000,
          surplus_gbp: 4000,
          transaction_count: 40,
          coverage_note: "Showing available history from 2026-05-17 (3 of 6 months).",
          empty: false,
          compare_label: "Prior 6 months",
          compare_date_from: "2025-08-19",
          compare_date_to: "2026-02-18",
          compare_income_gbp: 0,
          compare_spending_gbp: 0,
          compare_surplus_gbp: 0,
          compare_transaction_count: 0,
          compare_coverage_note:
            "No stored transactions in 6 months (2025-08-19 to 2026-02-18).",
          compare_empty: true,
          income_change_gbp: null,
          spending_change_gbp: null,
          surplus_change_gbp: null,
        },
      ],
    })),
  },
}));

describe("PlComparePanel", () => {
  it("does not show current-window empty copy when figures exist but compare is empty", async () => {
    render(<PlComparePanel scope="personal" title="Personal profit & loss compare" />);
    expect(await screen.findByText("£12,000.00")).toBeInTheDocument();
    expect(screen.getByText("£8,000.00")).toBeInTheDocument();
    expect(screen.getByText("£4,000.00")).toBeInTheDocument();
    expect(
      screen.getByText("Showing available history from 2026-05-17 (3 of 6 months)."),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/No prior 6 months data to compare yet/i).length).toBeGreaterThan(
      0,
    );
    expect(screen.queryByText(/No stored transactions in 6 months/)).not.toBeInTheDocument();
  });
});
