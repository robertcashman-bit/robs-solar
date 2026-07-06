import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FinanceAlertsPanel } from "@/components/finance/FinanceAlertsPanel";
import type { FinanceInsight } from "@/lib/finance-schemas";

const sampleInsights: FinanceInsight[] = [
  {
    id: 1,
    category: "cashflow",
    severity: "warning",
    title: "Personal cash may be tight after expected bills",
    message: "After household bills, about 0 GBP remains in personal accounts.",
    status: "active",
    created_at: "2026-07-03T00:00:00Z",
  },
  {
    id: 2,
    category: "business",
    severity: "warning",
    title: "You may be drawing too much from the business this month",
    message: "Director's loan balance is 16951 GBP while business cash is limited.",
    status: "active",
    created_at: "2026-07-03T00:00:00Z",
  },
  {
    id: 3,
    category: "tax",
    severity: "info",
    title: "Corporation tax reserve may be low",
    message: "Corp tax reserve is 0 GBP relative to estimated profit.",
    status: "active",
    created_at: "2026-07-03T00:00:00Z",
  },
];

describe("FinanceAlertsPanel", () => {
  it("shows warnings prominently at the top with links", () => {
    render(<FinanceAlertsPanel insights={sampleInsights} />);
    expect(screen.getByText("Alerts & recommendations")).toBeInTheDocument();
    expect(screen.getByText("2 items need attention")).toBeInTheDocument();
    expect(screen.getByText("Personal cash may be tight after expected bills")).toBeInTheDocument();
    expect(screen.getAllByText(/View cash flow/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/1 more recommendation/)).toBeInTheDocument();
  });
});
