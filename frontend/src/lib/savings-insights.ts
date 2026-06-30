import type { LiveMetrics, MetricSummary } from "@/lib/schemas";

export type InsightSeverity = "positive" | "neutral" | "warning" | "action";

export type SavingsInsight = {
  id: string;
  severity: InsightSeverity;
  title: string;
  body: string;
  actionLabel?: string;
  actionHref?: string;
};

const BATTERY_KWH = 16.1;

function batteryPower(metrics: LiveMetrics): number {
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

export type SavingsInsightOptions = {
  importRatePence?: number | null;
  exportRatePence?: number | null;
  tariffFamily?: string | null;
  agilePricePence?: number | null;
};

export function buildSavingsInsights(
  metrics: LiveMetrics,
  summary: MetricSummary | null,
  options?: SavingsInsightOptions,
): SavingsInsight[] {
  const insights: SavingsInsight[] = [];
  const batt = batteryPower(metrics);
  const importing = metrics.grid_import_w > 100;
  const exporting = metrics.grid_export_w > 100;
  const sunny = metrics.pv_power_w > 1500;
  const importP = options?.importRatePence ?? null;
  const exportP = options?.exportRatePence ?? null;
  const agileP = options?.agilePricePence ?? null;
  const family = options?.tariffFamily ?? "";

  if (importP != null && family === "IOG") {
    insights.push({
      id: "iog-tariff-context",
      severity: "neutral",
      title: "Intelligent Octopus Go rates applied",
      body: `Savings use your import rate of ${importP.toFixed(1)}p/kWh${
        exportP != null ? ` and export at ${exportP.toFixed(1)}p/kWh` : ""
      }. Self-consuming solar avoids the higher import cost.`,
    });
  }

  if (summary && summary.savings > 0) {
    insights.push({
      id: "savings-positive",
      severity: "positive",
      title: `Saving ${summary.currency === "GBP" ? "£" : ""}${summary.savings.toFixed(2)} today`,
      body: `Your solar is offsetting grid costs. Self-consumption is ${summary.self_consumption_pct.toFixed(0)}% of generation.`,
    });
  }

  if (importing && sunny) {
    insights.push({
      id: "import-while-sunny",
      severity: "warning",
      title: "Importing while solar is generating",
      body: `${Math.round(metrics.grid_import_w)} W from grid despite ${Math.round(metrics.pv_power_w)} W PV. Check load timing or battery mode.`,
      actionLabel: "Review controls",
      actionHref: "/controls",
    });
  }

  if (
    agileP != null &&
    importing &&
    agileP < 8 &&
    (importP == null || agileP < importP * 0.6)
  ) {
    insights.push({
      id: "cheap-agile-market",
      severity: "action",
      title: "Agile market dip",
      body: `Wholesale Agile is ${agileP.toFixed(1)}p/kWh — well below your bill rate. Worth checking if grid charging makes sense.`,
      actionLabel: "View Octopus",
      actionHref: "/octopus",
    });
  }

  if (agileP != null && exporting && agileP > 30) {
    insights.push({
      id: "expensive-agile-market",
      severity: "neutral",
      title: "High Agile market period",
      body: `Agile wholesale is ${agileP.toFixed(1)}p/kWh — exporting surplus may earn more than usual.`,
      actionHref: "/octopus",
      actionLabel: "View prices",
    });
  }

  if (
    exporting &&
    exportP != null &&
    importP != null &&
    exportP < importP * 0.6
  ) {
    insights.push({
      id: "export-vs-import",
      severity: "neutral",
      title: "Export earns less than import costs",
      body: `You export at ${exportP.toFixed(1)}p/kWh but import at ${importP.toFixed(1)}p/kWh. Favour battery or self-use before exporting.`,
      actionLabel: "Scheduler",
      actionHref: "/scheduler",
    });
  }

  if (metrics.battery_soc_pct < 25 && metrics.pv_power_w < 500 && !importing) {
    insights.push({
      id: "low-soc-evening",
      severity: "warning",
      title: "Battery running low",
      body: `SOC is ${metrics.battery_soc_pct.toFixed(0)}% with little solar. Consider overnight grid charge if tomorrow looks cloudy.`,
      actionLabel: "Check forecast",
      actionHref: "/forecast",
    });
  }

  if (metrics.battery_soc_pct > 90 && exporting && batt < -200) {
    const exportNote =
      exportP != null ? ` Export earns about ${exportP.toFixed(1)}p/kWh.` : "";
    insights.push({
      id: "battery-full-exporting",
      severity: "positive",
      title: "Battery full — exporting surplus",
      body: `Your battery is near full and sending excess to the grid.${exportNote}`,
    });
  }

  if (exporting && metrics.house_load_w > metrics.pv_power_w + 200) {
    insights.push({
      id: "export-under-load",
      severity: "neutral",
      title: "Exporting while home load is high",
      body: "You are exporting to grid while the house still draws significant power. Self-consumption mode may reduce import later.",
      actionLabel: "Scheduler",
      actionHref: "/scheduler",
    });
  }

  const hoursToFull =
    batt > 50
      ? (((100 - metrics.battery_soc_pct) / 100) * BATTERY_KWH) / (batt / 1000)
      : null;
  if (hoursToFull != null && hoursToFull < 2 && metrics.pv_power_w > 2000) {
    insights.push({
      id: "fast-charge",
      severity: "positive",
      title: "Battery charging quickly",
      body: `At current rate, full in about ${Math.ceil(hoursToFull * 60)} minutes from ${metrics.battery_soc_pct.toFixed(0)}% SOC.`,
    });
  }

  if (insights.length === 0) {
    insights.push({
      id: "all-good",
      severity: "neutral",
      title: "System looks balanced",
      body: "No immediate savings actions detected. Keep monitoring import/export through the day.",
    });
  }

  return insights.slice(0, 5);
}
