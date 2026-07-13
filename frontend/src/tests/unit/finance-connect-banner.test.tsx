import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FinanceConnectBanner } from "@/components/finance/FinanceConnectBanner";
import type { BankConnectionItem } from "@/lib/finance-schemas";

const openBankingCard: BankConnectionItem = {
  id: "lloyds",
  label: "Lloyds",
  method: "open_banking",
  status: "not_connected",
  status_message: "",
  account_count: 0,
  balance_gbp: 0,
};

describe("FinanceConnectBanner", () => {
  it("shows the Enable Banking activation nag when Open Banking is configured but not ready", () => {
    render(
      <FinanceConnectBanner
        connections={[openBankingCard]}
        obConfigured
        obReady={false}
      />,
    );
    expect(
      screen.getByText(/Open Banking needs activation before you can connect banks/i),
    ).toBeInTheDocument();
  });

  it("suppresses the Open Banking activation nag when Lunch Flow is the active provider", () => {
    // Regression: personal banks use Lunch Flow, so the legacy Enable Banking
    // activation prompt must not appear even when Open Banking is not ready.
    const { container } = render(
      <FinanceConnectBanner
        connections={[openBankingCard]}
        obConfigured
        obReady={false}
        lunchFlowActive
      />,
    );
    expect(
      screen.queryByText(/Open Banking needs activation/i),
    ).not.toBeInTheDocument();
    expect(container).toBeEmptyDOMElement();
  });
});
