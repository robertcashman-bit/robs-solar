import type { LiveMetrics, OctopusMeterPower } from "@/lib/schemas";

/** Below this wattage, treat power flow as idle (CT/meter jitter). */
export const POWER_NOISE_FLOOR_W = 5;

/** Show live watts on the diagram above this threshold (lower than noise floor). */
export const DISPLAY_WATTS_FLOOR_W = 1;

/** Above this wattage, animate flow connectors and node glow. */
export const FLOW_ANIMATION_THRESHOLD_W = 50;

/** When derived load exceeds reported by this much, CT is missing off-CT draw (EV). */
export const UNDERREPORTED_SLACK_W = 500;

/** Sunsynk load CT often reads 0 during export; allow this much balance slack. */
export const EXPORT_IMBALANCE_TOLERANCE_W = 30;

export type GridSublabel =
  | "Importing"
  | "Exporting"
  | "Exporting surplus"
  | "Selling to grid"
  | "Idle";

export type GridDisplayState = {
  importing: boolean;
  exporting: boolean;
  importAnimating: boolean;
  exportAnimating: boolean;
  value: string;
  sublabel: GridSublabel;
  watts: number;
};

type GridFlowMetrics = Pick<LiveMetrics, "grid_import_w" | "grid_export_w"> & {
  inverter_mode?: LiveMetrics["inverter_mode"];
};

function gridExportSublabel(inverterMode?: string): GridSublabel {
  if (inverterMode === "feed_in") {
    return "Selling to grid";
  }
  if (
    inverterMode === "self_use" ||
    inverterMode === "backup" ||
    inverterMode === "off_grid"
  ) {
    return "Exporting surplus";
  }
  return "Exporting";
}

export type HouseLoadSource =
  | "reported"
  | "derived"
  | "day_series"
  | "recent_typical"
  | "minimal";

export type HouseLoadDisplay = {
  watts: number;
  value: string;
  sublabel?: string;
  isMinimal: boolean;
  source?: HouseLoadSource;
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

function minutesAgoLabel(isoTimestamp: string | null | undefined): string | undefined {
  if (!isoTimestamp) {
    return undefined;
  }
  const sampleAt = Date.parse(isoTimestamp);
  if (Number.isNaN(sampleAt)) {
    return undefined;
  }
  const minutes = Math.max(1, Math.round((Date.now() - sampleAt) / 60_000));
  if (minutes < 60) {
    return `~${minutes} min ago`;
  }
  return `~${Math.round(minutes / 60)} hr ago`;
}

function houseLoadSublabel(metrics: LiveMetrics, derivedOverride: boolean): string | undefined {
  if (derivedOverride) {
    return "Includes EV / off-CT load";
  }
  const source = metrics.house_load_source ?? "reported";
  if (source === "day_series") {
    return minutesAgoLabel(metrics.house_load_at) ?? "~5 min ago";
  }
  if (source === "recent_typical") {
    return "Typical when drawing";
  }
  if (source === "derived") {
    const reported = metrics.house_load_reported_w ?? metrics.house_load_w;
    const offCt =
      reported > POWER_NOISE_FLOOR_W &&
      metrics.grid_import_w > reported + UNDERREPORTED_SLACK_W;
    return offCt ? "Includes EV / off-CT load" : "Estimated from balance";
  }
  if (source === "minimal") {
    return "Surplus to grid";
  }
  return undefined;
}

/** Short badge when load is inferred rather than CT-reported (for transparency chips). */
export function loadSourceBadge(
  metrics: LiveMetrics,
  display: HouseLoadDisplay,
): string | null {
  if (display.isMinimal) {
    return null;
  }
  const source = display.source ?? metrics.house_load_source ?? "reported";
  if (source === "derived") {
    return "Load estimated from balance";
  }
  if (source === "day_series") {
    const age = minutesAgoLabel(metrics.house_load_at);
    return age ? `Load from chart · ${age}` : "Load from today's chart";
  }
  if (source === "recent_typical") {
    return "Typical load when drawing";
  }
  return null;
}

function formatIntervalClock(iso: string): string {
  const date = Date.parse(iso);
  if (Number.isNaN(date)) {
    return iso;
  }
  return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(date);
}

/** Octopus half-hourly smart meter estimate for dashboard display. */
export function octopusMeterPowerDisplay(
  meter: OctopusMeterPower | null | undefined,
): { headline: string; detail: string } | null {
  if (!meter?.configured || meter.average_power_w == null) {
    return null;
  }
  const start = meter.interval_start ? formatIntervalClock(meter.interval_start) : null;
  const end = meter.interval_end ? formatIntervalClock(meter.interval_end) : null;
  const slot = start && end ? `${start}–${end}` : "latest half hour";
  const phase = meter.is_current_interval ? "in progress" : "last completed";
  const kwh = meter.consumption_kwh?.toFixed(3) ?? "—";
  return {
    headline: `${Math.round(meter.average_power_w).toLocaleString()} W average`,
    detail: `Smart meter · ${kwh} kWh · ${slot} (${phase}) · updates every 30 min`,
  };
}

export function balanceDerivedLoad(metrics: LiveMetrics, batteryPowerW: number): number {
  return metrics.pv_power_w + metrics.grid_import_w - metrics.grid_export_w + batteryPowerW;
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
  return deriveHouseLoadDisplay(metrics, batteryPowerW).watts;
}

/** House load for display — handles export-heavy snapshots where load CT reads 0. */
export function deriveHouseLoadDisplay(
  metrics: LiveMetrics,
  batteryPowerW: number,
): HouseLoadDisplay {
  const source = metrics.house_load_source ?? "reported";
  const derived = balanceDerivedLoad(metrics, batteryPowerW);
  const reported = metrics.house_load_reported_w ?? metrics.house_load_w;
  const derivedOverride =
    reported > POWER_NOISE_FLOOR_W && derived > reported + UNDERREPORTED_SLACK_W;

  if (metrics.house_load_w > POWER_NOISE_FLOOR_W) {
    const watts = derivedOverride ? derived : metrics.house_load_w;
    return {
      watts,
      value: formatPowerW(watts),
      sublabel: houseLoadSublabel(metrics, derivedOverride),
      isMinimal: false,
      source: derivedOverride ? "derived" : source,
    };
  }

  if (source === "minimal") {
    const raw = derived;
    const exporting = metrics.grid_export_w > POWER_NOISE_FLOOR_W;
    const generating =
      metrics.pv_power_w > POWER_NOISE_FLOOR_W ||
      Math.abs(batteryPowerW) > POWER_NOISE_FLOOR_W;

    if (exporting && generating && raw > -EXPORT_IMBALANCE_TOLERANCE_W) {
      return {
        watts: 0,
        value: "Minimal",
        sublabel: "Surplus to grid",
        isMinimal: true,
        source: "minimal",
      };
    }
  }

  if (derived > DISPLAY_WATTS_FLOOR_W && reported <= POWER_NOISE_FLOOR_W) {
    return {
      watts: derived,
      value: formatPowerW(derived),
      sublabel: houseLoadSublabel(
        metrics,
        reported > POWER_NOISE_FLOOR_W &&
          metrics.grid_import_w > reported + UNDERREPORTED_SLACK_W,
      ) ?? "Estimated from balance",
      isMinimal: false,
      source: "derived",
    };
  }

  if (derived > POWER_NOISE_FLOOR_W) {
    return {
      watts: derived,
      value: formatPowerW(derived),
      sublabel: houseLoadSublabel(
        metrics,
        reported > POWER_NOISE_FLOOR_W &&
          metrics.grid_import_w > reported + UNDERREPORTED_SLACK_W,
      ),
      isMinimal: false,
      source: "derived",
    };
  }

  return {
    watts: Math.max(0, metrics.house_load_w),
    value: "0 W",
    isMinimal: false,
    source,
  };
}

export function deriveInverterOutput(houseLoadW: number, gridExportW: number): number {
  return houseLoadW + gridExportW;
}

/** Inverter throughput from balance when load/export CT reads are near zero. */
export function deriveInverterOutputDisplay(
  metrics: LiveMetrics,
  houseLoadW: number,
  batteryPowerW: number,
): number {
  const fromLoad = houseLoadW + metrics.grid_export_w;
  const fromSupply = Math.max(
    0,
    metrics.pv_power_w + metrics.grid_import_w + batteryPowerW - metrics.grid_export_w,
  );
  return Math.max(fromLoad, fromSupply);
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

export function selfConsumptionPctFromLive(metrics: LiveMetrics): number {
  if (metrics.daily_pv_kwh <= 0) {
    return 0;
  }
  const selfConsumed = Math.max(0, metrics.daily_pv_kwh - metrics.daily_export_kwh);
  return Math.min(100, (selfConsumed / metrics.daily_pv_kwh) * 100);
}

export function gridDisplayState(metrics: GridFlowMetrics): GridDisplayState {
  const importW = metrics.grid_import_w;
  const exportW = metrics.grid_export_w;
  const importing = importW > DISPLAY_WATTS_FLOOR_W;
  const exporting = exportW > DISPLAY_WATTS_FLOOR_W;
  const importAnimating = importW > FLOW_ANIMATION_THRESHOLD_W;
  const exportAnimating = exportW > FLOW_ANIMATION_THRESHOLD_W;

  if (exporting && exportW >= importW) {
    return {
      importing,
      exporting,
      importAnimating,
      exportAnimating,
      value: formatPowerW(exportW),
      sublabel: gridExportSublabel(metrics.inverter_mode),
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
  metrics: GridFlowMetrics,
): { text: string; tone: "export" | "import" | "neutral" } {
  if (metrics.grid_export_w > DISPLAY_WATTS_FLOOR_W) {
    const watts = Math.round(metrics.grid_export_w);
    if (metrics.inverter_mode === "feed_in") {
      return { text: `Selling ${watts} W`, tone: "export" };
    }
    if (
      metrics.inverter_mode === "self_use" ||
      metrics.inverter_mode === "backup" ||
      metrics.inverter_mode === "off_grid"
    ) {
      return { text: `Surplus export ${watts} W`, tone: "export" };
    }
    return { text: `Export ${watts} W`, tone: "export" };
  }
  if (metrics.grid_import_w > DISPLAY_WATTS_FLOOR_W) {
    return { text: `Import ${Math.round(metrics.grid_import_w)} W`, tone: "import" };
  }
  return { text: "Grid idle", tone: "neutral" };
}
