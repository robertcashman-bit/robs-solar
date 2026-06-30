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
  cheap_now: false,
  offpeak_start: "23:30",
  offpeak_end: "05:30",
  next_cheap_start: null,
  next_cheap_source: "",
  state: "idle",
  severity: "good",
};

describe("CheapWindowBanner", () => {
  it("renders nothing when status is null", () => {
    const { container } = render(<CheapWindowBanner status={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows cheap rate now when cheap_now is true", () => {
    render(
      <CheapWindowBanner
        status={{
          ...base,
          cheap_now: true,
          source: "off-peak",
          state: "idle",
        }}
      />,
    );
    expect(screen.getByText(/cheap rate now/i)).toBeInTheDocument();
  });

  it("shows peak rate now and next window when not cheap", () => {
    render(
      <CheapWindowBanner
        status={{
          ...base,
          cheap_now: false,
          next_cheap_start: "2026-06-30T22:30:00Z",
          next_cheap_source: "off-peak",
        }}
      />,
    );
    expect(screen.getByText(/peak rate now/i)).toBeInTheDocument();
  });

  it("shows intentional import explainer for cheap import", () => {
    render(
      <CheapWindowBanner
        status={{
          ...base,
          importing_on_cheap_window: true,
          cheap_now: true,
          state: "cheap_import",
          severity: "good",
          message: "Importing 0.4 kW from the grid on cheap power.",
        }}
      />,
    );
    expect(screen.getByText(/this is intentional/i)).toBeInTheDocument();
  });

  it("shows peak import explanation", () => {
    render(
      <CheapWindowBanner
        status={{
          ...base,
          state: "peak_import",
          severity: "info",
          message: "Importing 0.8 kW at the peak day rate.",
        }}
      />,
    );
    expect(screen.getByText(/importing at peak rate/i)).toBeInTheDocument();
    expect(screen.getByText(/peak day rate/i)).toBeInTheDocument();
  });

  it("shows a warning when grid-charging without a matching cheap window", () => {
    render(
      <CheapWindowBanner
        status={{
          ...base,
          active: true,
          source: "unexpected",
          state: "peak_import",
          severity: "caution",
          grid_import_w: 300,
          message: "The inverter is importing while grid-charge is enabled, but no cheap window matches.",
        }}
      />,
    );
    expect(screen.getByText(/unexpected grid import/i)).toBeInTheDocument();
  });
});
