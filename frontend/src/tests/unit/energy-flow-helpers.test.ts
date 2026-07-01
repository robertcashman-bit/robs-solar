import { describe, expect, it } from "vitest";

import {
  batteryDisplayState,
  deriveHouseLoad,
  deriveHouseLoadDisplay,
  deriveInverterOutput,
  deriveInverterOutputDisplay,
  isInverterMeterLimited,
  loadSourceBadge,
  octopusMeterPowerDisplay,
  energyBalanceError,
  gridDisplayState,
  gridHeroLabel,
  selfConsumptionPctFromLive,
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

  it("gridDisplayState treats sub-display floor grid as idle", () => {
    const state = gridDisplayState({ grid_import_w: 0.5, grid_export_w: 0 });
    expect(state.value).toBe("0 W");
    expect(state.sublabel).toBe("Idle");
  });

  it("gridDisplayState shows Exporting surplus in self use mode", () => {
    const state = gridDisplayState({
      grid_import_w: 0,
      grid_export_w: 20,
      inverter_mode: "self_use",
    });
    expect(state.sublabel).toBe("Exporting surplus");
  });

  it("gridDisplayState shows Selling to grid in feed-in mode", () => {
    const state = gridDisplayState({
      grid_import_w: 0,
      grid_export_w: 2500,
      inverter_mode: "feed_in",
    });
    expect(state.sublabel).toBe("Selling to grid");
  });

  it("gridHeroLabel shows surplus export wording in self use mode", () => {
    const label = gridHeroLabel({
      grid_import_w: 0,
      grid_export_w: 20,
      inverter_mode: "self_use",
    });
    expect(label.text).toBe("Surplus export 20 W");
    expect(label.tone).toBe("export");
  });

  it("gridHeroLabel shows selling wording in feed-in mode", () => {
    const label = gridHeroLabel({
      grid_import_w: 0,
      grid_export_w: 2500,
      inverter_mode: "feed_in",
    });
    expect(label.text).toBe("Selling 2500 W");
    expect(label.tone).toBe("export");
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
    const balanced = {
      ...baseMetrics,
      pv_power_w: 1700,
      grid_import_w: 0,
      grid_export_w: 500,
      house_load_w: 1800,
      battery_power_w: 600,
    };
    expect(deriveHouseLoad(balanced, 600)).toBe(1800);
  });

  it("selfConsumptionPctFromLive matches Today card formula", () => {
    expect(selfConsumptionPctFromLive(baseMetrics)).toBeCloseTo(53.2, 0);
  });

  it("deriveInverterOutput equals home load plus export", () => {
    expect(deriveInverterOutput(20, 0)).toBe(20);
    expect(deriveInverterOutput(1800, 500)).toBe(2300);
  });

  it("deriveInverterOutputDisplay uses supply balance when load CT is zero", () => {
    const metrics = {
      ...baseMetrics,
      pv_power_w: 12,
      grid_import_w: 13,
      grid_export_w: 0,
      house_load_w: 0,
      battery_power_w: 0,
    };
    expect(deriveInverterOutputDisplay(metrics, 0, 0)).toBe(25);
  });

  it("deriveHouseLoadDisplay shows derived load when CT reads zero", () => {
    const metrics = {
      ...baseMetrics,
      pv_power_w: 12,
      grid_import_w: 13,
      grid_export_w: 0,
      house_load_w: 0,
      house_load_source: "minimal" as const,
      battery_power_w: 0,
    };
    const display = deriveHouseLoadDisplay(metrics, 0);
    expect(display.value).toBe("25 W");
    expect(display.isMinimal).toBe(false);
    expect(display.source).toBe("derived");
  });

  it("loadSourceBadge explains derived load for transparency", () => {
    const metrics = {
      ...baseMetrics,
      pv_power_w: 9,
      grid_import_w: 12,
      grid_export_w: 0,
      house_load_w: 22,
      house_load_source: "derived" as const,
      house_load_reported_w: 0,
      battery_power_w: 1,
    };
    const display = deriveHouseLoadDisplay(metrics, 1);
    expect(loadSourceBadge(metrics, display)).toBe("Load estimated from balance");
  });

  it("isInverterMeterLimited when grid meter null and load derived", () => {
    const metrics = {
      ...baseMetrics,
      pv_power_w: 17,
      grid_import_w: 12,
      grid_export_w: 0,
      house_load_w: 30,
      house_load_source: "derived" as const,
      house_load_reported_w: 0,
      battery_power_w: 1,
      grid_meter_connected: null,
    };
    expect(isInverterMeterLimited(metrics, null, 30)).toBe(true);
  });

  it("isInverterMeterLimited when Octopus reads much higher than inverter load", () => {
    const metrics = {
      ...baseMetrics,
      pv_power_w: 17,
      grid_import_w: 0,
      house_load_w: 30,
      house_load_source: "reported" as const,
      grid_meter_connected: true,
    };
    expect(
      isInverterMeterLimited(
        metrics,
        {
          configured: true,
          average_power_w: 376,
          consumption_kwh: 0.188,
          interval_start: "2026-07-01T19:00:00Z",
          interval_end: "2026-07-01T19:30:00Z",
          is_current_interval: true,
          message: "",
        },
        30,
      ),
    ).toBe(true);
  });

  it("isInverterMeterLimited uses smart_meter_average_w from live metrics", () => {
    const metrics = {
      ...baseMetrics,
      pv_power_w: 17,
      house_load_w: 30,
      house_load_source: "reported" as const,
      grid_meter_connected: true,
      smart_meter_average_w: 376,
    };
    expect(isInverterMeterLimited(metrics, null, 30)).toBe(true);
  });

  it("isInverterMeterLimited false when CT connected and loads align", () => {
    const metrics = {
      ...baseMetrics,
      house_load_w: 1800,
      house_load_source: "reported" as const,
      grid_meter_connected: true,
    };
    expect(isInverterMeterLimited(metrics, null, 1800)).toBe(false);
  });

  it("octopusMeterPowerDisplay formats half-hour average", () => {
    const display = octopusMeterPowerDisplay({
      configured: true,
      average_power_w: 376,
      consumption_kwh: 0.188,
      interval_start: "2026-07-01T19:00:00Z",
      interval_end: "2026-07-01T19:30:00Z",
      is_current_interval: true,
      message: "",
    });
    expect(display?.headline).toBe("376 W average");
    expect(display?.isLive).toBe(false);
    expect(display?.detail).toContain("Electricity meter");
    expect(display?.detail).toContain("in progress");
  });

  it("octopusMeterPowerDisplay prefers live watts when available", () => {
    const display = octopusMeterPowerDisplay({
      configured: true,
      average_power_w: 300,
      consumption_kwh: 0.15,
      interval_start: "2026-07-01T19:00:00Z",
      interval_end: "2026-07-01T19:30:00Z",
      is_current_interval: true,
      live_available: true,
      live_demand_w: 376,
      message: "",
    });
    expect(display?.isLive).toBe(true);
    expect(display?.headline).toBe("376 W now");
    expect(display?.liveW).toBe(376);
    expect(display?.averageHeadline).toBe("300 W average");
    expect(display?.detail).toContain("Live whole-home draw");
  });

  it("octopusMeterPowerDisplay falls back to 30-min average when live absent", () => {
    const display = octopusMeterPowerDisplay({
      configured: true,
      average_power_w: 300,
      consumption_kwh: 0.15,
      live_available: false,
      message: "",
    });
    expect(display?.isLive).toBe(false);
    expect(display?.headline).toBe("300 W average");
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

  it("deriveHouseLoadDisplay shows Minimal during export-heavy low load", () => {
    const metrics = {
      ...baseMetrics,
      pv_power_w: 95,
      grid_import_w: 0,
      grid_export_w: 125,
      house_load_w: 0,
      house_load_source: "minimal" as const,
      battery_power_w: 26,
    };
    const display = deriveHouseLoadDisplay(metrics, 26);
    expect(display.value).toBe("Minimal");
    expect(display.sublabel).toBe("Surplus to grid");
    expect(display.isMinimal).toBe(true);
  });

  it("deriveHouseLoadDisplay shows day-series load with age sublabel", () => {
    const metrics = {
      ...baseMetrics,
      pv_power_w: 95,
      grid_import_w: 0,
      grid_export_w: 125,
      house_load_w: 420,
      house_load_source: "day_series" as const,
      house_load_at: new Date(Date.now() - 5 * 60_000).toISOString(),
      battery_power_w: 26,
    };
    const display = deriveHouseLoadDisplay(metrics, 26);
    expect(display.value).toBe("420 W");
    expect(display.sublabel).toMatch(/min ago/);
    expect(display.isMinimal).toBe(false);
  });

  it("deriveHouseLoadDisplay shows recent typical load", () => {
    const metrics = {
      ...baseMetrics,
      pv_power_w: 95,
      grid_import_w: 0,
      grid_export_w: 125,
      house_load_w: 380,
      house_load_source: "recent_typical" as const,
      battery_power_w: 26,
    };
    const display = deriveHouseLoadDisplay(metrics, 26);
    expect(display.value).toBe("380 W");
    expect(display.sublabel).toBe("Typical when drawing");
  });

  it("deriveHouseLoadDisplay overrides under-reported CT during EV charge", () => {
    const metrics = {
      ...baseMetrics,
      pv_power_w: 0,
      grid_import_w: 7200,
      grid_export_w: 0,
      house_load_w: 250,
      house_load_source: "derived" as const,
      battery_power_w: 0,
    };
    const display = deriveHouseLoadDisplay(metrics, 0);
    expect(display.value).toBe("7,200 W");
    expect(display.sublabel).toBe("Includes EV / off-CT load");
  });
});
