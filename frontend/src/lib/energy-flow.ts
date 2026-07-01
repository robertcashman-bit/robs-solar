import type { LiveMetrics } from "@/lib/schemas";

/** Below this wattage, treat power flow as idle (CT/meter jitter). */
export const POWER_NOISE_FLOOR_W = 5;

/** Above this wattage, animate flow connectors and node glow. */
export const FLOW_ANIMATION_THRESHOLD_W = 50;

export type GridDisplayState = {
  importing: boolean;
  exporting: boolean;
  importAnimating: boolean;
  exportAnimating: boolean;
  value: string;
  sublabel: "Importing" | "Exporting" | "Idle";
  watts: number;
};

export type BatteryDisplayState = {
  charging: boolean;
  discharging: boolean;
  animating: boolean;
  sublabel: string;
};

export function formatPowerW(value: number): string {
  return `${Math.round(Math.abs(value)).toLocaleString()} W`;
}

/** Battery power in app convention: positive = discharging. */
export function resolveBatteryPower(metrics: LiveMetrics): number {
  if (metrics.battery_power_w != null) {
    return metrics.battery_power_w;
  }
  return (
    metrics.pv_power_w +
    metrics.grid_import_w -
    metrics.house_load_w -
    metrics.grid_export_w
  );
}

/** Instantaneous house load from API or power balance. */
export function deriveHouseLoad(metrics: LiveMetrics, batteryPowerW: number): number {
  if (metrics.house_load_w > POWER_NOISE_FLOOR_W) {
    return metrics.house_load_w;
  }
  const derived =
    metrics.pv_power_w + metrics.grid_import_w - metrics.grid_export_w + batteryPowerW;
  return derived > POWER_NOISE_FLOOR_W ? derived : metrics.house_load_w;
}

export function deriveInverterOutput(houseLoadW: number, gridExportW: number): number {
  return houseLoadW + gridExportW;
}

export function batteryDisplayState(batteryPowerW: number): BatteryDisplayState {
  const charging = batteryPowerW < -POWER_NOISE_FLOOR_W;
  const discharging = batteryPowerW > POWER_NOISE_FLOOR_W;
  const animating = Math.abs(batteryPowerW) > FLOW_ANIMATION_THRESHOLD_W;
  const sublabel =
    charging || discharging
      ? `${formatPowerW(batteryPowerW)} ${charging ? "Charging" : "Discharging"}`
      : "Idle";
  return { charging, discharging, animating, sublabel };
}

/** Absolute power balance error (W). Should be near zero for consistent metrics. */
export function energyBalanceError(metrics: LiveMetrics): number {
  const batteryPowerW = resolveBatteryPower(metrics);
  const houseLoadW = deriveHouseLoad(metrics, batteryPowerW);
  const supply =
    metrics.pv_power_w + metrics.grid_import_w - metrics.grid_export_w + batteryPowerW;
  return Math.abs(houseLoadW - supply);
}

export function gridDisplayState(
  metrics: Pick<LiveMetrics, "grid_import_w" | "grid_export_w">,
): GridDisplayState {
  const importW = metrics.grid_import_w;
  const exportW = metrics.grid_export_w;
  const importing = importW > POWER_NOISE_FLOOR_W;
  const exporting = exportW > POWER_NOISE_FLOOR_W;
  const importAnimating = importW > FLOW_ANIMATION_THRESHOLD_W;
  const exportAnimating = exportW > FLOW_ANIMATION_THRESHOLD_W;

  if (exporting && exportW >= importW) {
    return {
      importing,
      exporting,
      importAnimating,
      exportAnimating,
      value: formatPowerW(exportW),
      sublabel: "Exporting",
      watts: exportW,
    };
  }
  if (importing) {
    return {
      importing,
      exporting,
      importAnimating,
      exportAnimating,
      value: formatPowerW(importW),
      sublabel: "Importing",
      watts: importW,
    };
  }
  return {
    importing: false,
    exporting: false,
    importAnimating,
    exportAnimating,
    value: "0 W",
    sublabel: "Idle",
    watts: 0,
  };
}

export function gridHeroLabel(
  metrics: Pick<LiveMetrics, "grid_import_w" | "grid_export_w">,
): { text: string; tone: "export" | "import" | "neutral" } {
  if (metrics.grid_export_w > POWER_NOISE_FLOOR_W) {
    return { text: `Export ${Math.round(metrics.grid_export_w)} W`, tone: "export" };
  }
  if (metrics.grid_import_w > POWER_NOISE_FLOOR_W) {
    return { text: `Import ${Math.round(metrics.grid_import_w)} W`, tone: "import" };
  }
  return { text: "Grid idle", tone: "neutral" };
}
