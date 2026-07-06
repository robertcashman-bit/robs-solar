import { describe, expect, it } from "vitest";

import { loadDiagnosticsSchema } from "@/lib/schemas";

describe("loadDiagnosticsSchema", () => {
  it("parses a realistic live sunsynk_connect diagnostics payload", () => {
    const payload = {
      timestamp: "2026-07-06T06:01:45.056712+00:00",
      adapter_mode: "sunsynk_connect",
      data_source: "live",
      is_cached: false,
      cache_age_seconds: 0,
      raw_payload: { pvPower: 33, loadOrEpsPower: 0, gridOrMeterPower: 12, existsMeter: false },
      raw_payload_captured_at: "2026-07-06T06:01:45.0Z",
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

    const parsed = loadDiagnosticsSchema.parse(payload);
    expect(parsed.house_load_w).toBe(188);
    expect(parsed.measured_load_w).toBe(0);
    expect(parsed.estimated_load_w).toBe(188);
    expect(parsed.grid_meter_connected).toBe(false);
  });

  it("parses a graceful degraded payload with no raw payload and unknown fields", () => {
    const payload = {
      timestamp: "2026-07-06T06:01:45Z",
      adapter_mode: "simulator",
      data_source: "simulated",
      is_cached: false,
      cache_age_seconds: null,
      raw_payload: null,
      raw_payload_captured_at: null,
      raw_payload_note: "This adapter does not expose a raw cloud/API payload.",
      pv: { label: "Solar (PV)", value: null, unit: "W", origin: "unknown" },
      battery: { label: "Battery", value: null, unit: "W", origin: "unknown" },
      grid_import: { label: "Grid import", value: null, unit: "W", origin: "unknown" },
      grid_export: { label: "Grid export", value: null, unit: "W", origin: "unknown" },
      measured_load_w: null,
      measured_load_origin: "unknown",
      estimated_load_w: null,
      estimated_load_formula: "pv_power_w + grid_import_w - grid_export_w + battery_power_w",
      house_load_source: "minimal",
      house_load_w: 0,
      house_load_at: null,
      grid_meter_connected: null,
    };

    const parsed = loadDiagnosticsSchema.parse(payload);
    expect(parsed.raw_payload).toBeNull();
    expect(parsed.pv.value).toBeNull();
    expect(parsed.pv.origin).toBe("unknown");
  });
});
