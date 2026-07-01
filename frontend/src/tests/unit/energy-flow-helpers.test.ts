import { describe, expect, it } from "vitest";

import {
  batteryDisplayState,
  deriveHouseLoad,
  deriveInverterOutput,
  energyBalanceError,
  gridDisplayState,
  gridHeroLabel,
  resolveBatteryPower,
} from "@/lib/energy-flow";
import type { LiveMetrics } from "@/lib/schemas";

const baseMetrics: LiveMetrics = {
  pv_power_w: 4200,
  battery_soc_pct: 68,
  battery_power_w: 600,
  house_load_w: 1800,
  grid_import_w: 0,
  grid_export_w: 500,
  inverter_mode: "self_use",
  inverter_status: "online",
  daily_pv_kwh: 12.4,
  daily_import_kwh: 3.1,
  daily_export_kwh: 5.8,
  timestamp: new Date().toISOString(),
};

describe("energy-flow helpers", () => {
  it("gridDisplayState shows small import above noise floor", () => {
    const state = gridDisplayState({ grid_import_w: 13, grid_export_w: 0 });
    expect(state.value).toBe("13 W");
    expect(state.sublabel).toBe("Importing");
    expect(state.importing).toBe(true);
    expect(state.importAnimating).toBe(false);
  });

  it("gridHeroLabel shows small import instead of grid idle", () => {
    const label = gridHeroLabel({ grid_import_w: 13, grid_export_w: 0 });
    expect(label.text).toBe("Import 13 W");
    expect(label.tone).toBe("import");
  });

  it("gridDisplayState treats sub-noise grid as idle", () => {
    const state = gridDisplayState({ grid_import_w: 3, grid_export_w: 0 });
    expect(state.value).toBe("0 W");
    expect(state.sublabel).toBe("Idle");
  });

  it("deriveHouseLoad resolves low load from power balance", () => {
    const metrics = {
      ...baseMetrics,
      pv_power_w: 9,
      grid_import_w: 11,
      grid_export_w: 0,
      house_load_w: 0,
      battery_power_w: 0,
    };
    expect(deriveHouseLoad(metrics, 0)).toBe(20);
  });

  it("deriveHouseLoad prefers API when plausible", () => {
    expect(deriveHouseLoad(baseMetrics, 600)).toBe(1800);
  });

  it("deriveInverterOutput equals home load plus export", () => {
    expect(deriveInverterOutput(20, 0)).toBe(20);
    expect(deriveInverterOutput(1800, 500)).toBe(2300);
  });

  it("energyBalanceError is near zero for consistent metrics", () => {
    const metrics = {
      ...baseMetrics,
      pv_power_w: 9,
      grid_import_w: 11,
      grid_export_w: 0,
      house_load_w: 0,
      battery_power_w: 0,
    };
    expect(energyBalanceError(metrics)).toBeLessThan(2);
  });

  it("batteryDisplayState shows small discharge without animating", () => {
    const state = batteryDisplayState(40);
    expect(state.sublabel).toBe("40 W Discharging");
    expect(state.discharging).toBe(true);
    expect(state.animating).toBe(false);
  });

  it("batteryDisplayState shows idle below noise floor", () => {
    const state = batteryDisplayState(2);
    expect(state.sublabel).toBe("Idle");
    expect(state.animating).toBe(false);
  });

  it("resolveBatteryPower uses API value when provided", () => {
    expect(resolveBatteryPower({ ...baseMetrics, battery_power_w: 150 })).toBe(150);
  });
});
