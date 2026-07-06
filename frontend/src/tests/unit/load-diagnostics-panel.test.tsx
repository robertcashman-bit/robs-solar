import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LoadDiagnosticsPanel } from "@/components/diagnostics/LoadDiagnosticsPanel";
import type { LoadDiagnostics } from "@/lib/schemas";

const baseDiagnostics: LoadDiagnostics = {
  timestamp: new Date().toISOString(),
  adapter_mode: "sunsynk_connect",
  data_source: "live",
  is_cached: false,
  cache_age_seconds: 0,
  raw_payload: { pvPower: 33, loadOrEpsPower: 0, gridOrMeterPower: 12 },
  raw_payload_captured_at: new Date().toISOString(),
  raw_payload_note: null,
  pv: { label: "Solar (PV)", value: 33, unit: "W", origin: "live", source_field: "pv_power_w" },
  battery: {
    label: "Battery",
    value: 143,
    unit: "W",
    origin: "live",
    source_field: "battery_power_w",
  },
  grid_import: {
    label: "Grid import",
    value: 12,
    unit: "W",
    origin: "live",
    source_field: "grid_import_w",
  },
  grid_export: {
    label: "Grid export",
    value: 0,
    unit: "W",
    origin: "live",
    source_field: "grid_export_w",
  },
  measured_load_w: 0,
  measured_load_origin: "unknown",
  estimated_load_w: 188,
  estimated_load_formula: "pv_power_w + grid_import_w - grid_export_w + battery_power_w",
  house_load_source: "derived",
  house_load_w: 188,
  house_load_at: null,
  grid_meter_connected: false,
};

describe("LoadDiagnosticsPanel", () => {
  it("shows a loading state when there is no data yet", () => {
    render(<LoadDiagnosticsPanel diagnostics={null} loading />);
    expect(screen.getByText(/Loading diagnostics/i)).toBeInTheDocument();
  });

  it("shows an error banner when the fetch fails", () => {
    render(<LoadDiagnosticsPanel diagnostics={null} error="Network error" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Network error");
  });

  it("keeps Measured Load and Estimated Load visually separate", () => {
    render(<LoadDiagnosticsPanel diagnostics={baseDiagnostics} />);
    expect(screen.getByText("Measured Load")).toBeInTheDocument();
    expect(screen.getByText("Estimated Load")).toBeInTheDocument();
    // Measured is unknown (raw CT read 0 but we can't tell if that's real or missing).
    expect(screen.getByText("Unknown")).toBeInTheDocument();
    // Estimated is a real computed number (appears at least once).
    expect(screen.getAllByText("188 W").length).toBeGreaterThan(0);
  });

  it("warns about a missing grid meter when grid_meter_connected is false", () => {
    render(<LoadDiagnosticsPanel diagnostics={baseDiagnostics} />);
    expect(screen.getByText(/existsMeter=false/)).toBeInTheDocument();
    expect(screen.getByText(/physical installation issue/i)).toBeInTheDocument();
  });

  it("does not show the missing-meter warning when the meter is connected", () => {
    render(
      <LoadDiagnosticsPanel
        diagnostics={{ ...baseDiagnostics, grid_meter_connected: true }}
      />,
    );
    expect(screen.queryByText(/existsMeter=false/)).not.toBeInTheDocument();
  });

  it("renders the raw payload JSON before transformation", () => {
    render(<LoadDiagnosticsPanel diagnostics={baseDiagnostics} />);
    expect(screen.getByText(/"pvPower": 33/)).toBeInTheDocument();
    expect(screen.getByText(/"loadOrEpsPower": 0/)).toBeInTheDocument();
  });

  it("shows an explicit note instead of raw payload when the adapter has none", () => {
    render(
      <LoadDiagnosticsPanel
        diagnostics={{
          ...baseDiagnostics,
          raw_payload: null,
          raw_payload_note: "This adapter does not expose a raw cloud/API payload.",
        }}
      />,
    );
    expect(
      screen.getByText("This adapter does not expose a raw cloud/API payload."),
    ).toBeInTheDocument();
  });

  it("renders a field as Unknown (not 0) when its value is missing", () => {
    render(
      <LoadDiagnosticsPanel
        diagnostics={{
          ...baseDiagnostics,
          battery: { label: "Battery", value: null, unit: "W", origin: "unknown" },
        }}
      />,
    );
    const unknowns = screen.getAllByText("Unknown");
    expect(unknowns.length).toBeGreaterThan(0);
  });

  it("includes the physical/installation checklist", () => {
    render(<LoadDiagnosticsPanel diagnostics={baseDiagnostics} />);
    expect(screen.getByText(/CT clamp fitted in the wrong place/i)).toBeInTheDocument();
    expect(screen.getByText(/grid CT only/i)).toBeInTheDocument();
  });
});
