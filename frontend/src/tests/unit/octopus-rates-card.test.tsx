import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OctopusRatesCard } from "@/components/dashboard/OctopusRatesCard";
import type { OctopusRatePlan } from "@/lib/schemas";

const plan: OctopusRatePlan = {
  configured: true,
  tariff_family: "IOG",
  region: "J",
  import_display_name: "Intelligent Octopus Go",
  cheap_rate_pence: 7.0,
  peak_rate_pence: 28.6,
  cheap_windows: [{ start: "23:30", end: "05:30" }],
  peak_windows: [{ start: "05:30", end: "23:30" }],
  current_rate_pence: 28.6,
  current_is_cheap: false,
  planned_cheap_windows: [],
};

describe("OctopusRatesCard", () => {
  it("renders nothing when plan is not configured", () => {
    const { container } = render(<OctopusRatesCard plan={{ ...plan, configured: false }} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows cheap and peak tiers with active highlight", () => {
    render(<OctopusRatesCard plan={plan} />);
    expect(screen.getByText(/your octopus rates/i)).toBeInTheDocument();
    expect(screen.getByText(/7.0p/)).toBeInTheDocument();
    expect(screen.getByText(/peak rate/i)).toBeInTheDocument();
    expect(screen.getAllByText(/28\.6/).length).toBeGreaterThan(0);
    expect(screen.getByText(/active now/i)).toBeInTheDocument();
    expect(screen.getByText(/23:30–05:30/)).toBeInTheDocument();
  });
});
