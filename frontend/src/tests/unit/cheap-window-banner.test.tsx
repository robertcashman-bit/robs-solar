import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CheapWindowBanner } from "@/components/dashboard/CheapWindowBanner";
import type { ChargeWindowStatus } from "@/lib/schemas";

const base: ChargeWindowStatus = {
  importing_on_cheap_window: false,
  active: false,
  source: "",
  window_start: "",
  window_end: "",
  grid_import_w: 0,
  battery_soc_pct: 0,
  message: "",
};

describe("CheapWindowBanner", () => {
  it("renders nothing when status is null", () => {
    const { container } = render(<CheapWindowBanner status={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when not importing on a cheap window", () => {
    const { container } = render(<CheapWindowBanner status={base} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the intentional-import explainer when importing on a cheap window", () => {
    const status: ChargeWindowStatus = {
      ...base,
      importing_on_cheap_window: true,
      active: true,
      source: "smart-charge",
      window_start: "12:01",
      window_end: "12:30",
      grid_import_w: 389,
      battery_soc_pct: 100,
      message: "Importing from the grid on purpose. Normal discharge resumes at 12:30.",
    };
    render(<CheapWindowBanner status={status} />);
    expect(screen.getByText(/this is intentional/i)).toBeInTheDocument();
    expect(screen.getByText(/on purpose/i)).toBeInTheDocument();
  });

  it("shows a warning when grid-charging without a matching cheap window", () => {
    const status: ChargeWindowStatus = {
      ...base,
      active: true,
      source: "unexpected",
      grid_import_w: 300,
      message: "The inverter is importing while grid-charge is enabled, but no cheap window matches.",
    };
    render(<CheapWindowBanner status={status} />);
    expect(screen.getByText(/unexpected grid import/i)).toBeInTheDocument();
  });
});
