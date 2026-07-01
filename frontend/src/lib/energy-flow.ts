import type { LiveMetrics } from "@/lib/schemas";

/** Below this wattage, treat grid flow as idle (CT/meter jitter). */
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

export function formatPowerW(value: number): string {
  return `${Math.round(Math.abs(value)).toLocaleString()} W`;
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
