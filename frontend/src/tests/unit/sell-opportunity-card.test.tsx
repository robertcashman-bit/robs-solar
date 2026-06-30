import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SellOpportunityCard } from "@/components/dashboard/SellOpportunityCard";
import type { SellOpportunity } from "@/lib/schemas";

vi.mock("@/lib/api-client", () => ({
  apiClient: { post: vi.fn() },
  ApiError: class ApiError extends Error {},
}));

const base: SellOpportunity = {
  worth_selling: false,
  battery_soc_pct: 80,
  export_rate_pence: 10,
  import_rate_pence: 28,
  threshold_pence: 15,
  sellable_kwh: 0,
  estimated_value_gbp: 0,
  recommended_mode: "feed_in",
  headline: "Not worth selling right now",
  message: "Export is 10p/kWh, below your 15p threshold.",
  configured: true,
};

describe("SellOpportunityCard", () => {
  it("renders nothing when not configured", () => {
    const { container } = render(
      <SellOpportunityCard opportunity={{ ...base, configured: false }} canControl />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when opportunity is null", () => {
    const { container } = render(<SellOpportunityCard opportunity={null} canControl />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows headline and disables Sell now when not worth selling", () => {
    render(<SellOpportunityCard opportunity={base} canControl />);
    expect(screen.getByText(/not worth selling/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sell now/i })).toBeDisabled();
  });

  it("enables Sell now and shows value when worth selling", () => {
    const worth: SellOpportunity = {
      ...base,
      worth_selling: true,
      export_rate_pence: 22,
      sellable_kwh: 6.4,
      estimated_value_gbp: 1.41,
      headline: "Worth selling now at 22.0p/kWh",
      message: "Switch to Feed-in mode to export.",
    };
    render(<SellOpportunityCard opportunity={worth} canControl />);
    expect(screen.getByRole("button", { name: /sell now/i })).toBeEnabled();
    expect(screen.getByText(/£1\.41/)).toBeInTheDocument();
  });

  it("hides control buttons when the user cannot control", () => {
    render(<SellOpportunityCard opportunity={base} canControl={false} />);
    expect(screen.queryByRole("button", { name: /sell now/i })).not.toBeInTheDocument();
  });
});
