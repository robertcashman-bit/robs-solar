import { describe, expect, it } from "vitest";

import { buildSavingsInsights } from "@/lib/savings-insights";
import type { LiveMetrics, MetricSummary } from "@/lib/schemas";

const baseMetrics: LiveMetrics = {
  pv_power_w: 3000,
  battery_soc_pct: 45,
  battery_power_w: 500,
  house_load_w: 2000,
  grid_import_w: 0,
  grid_export_w: 1500,
  inverter_mode: "self_use",
  inverter_status: "online",
  daily_pv_kwh: 10,
  daily_import_kwh: 2,
  daily_export_kwh: 4,
  timestamp: new Date().toISOString(),
};

const summary: MetricSummary = {
  range: "day",
  pv_kwh: 10,
  consumption_kwh: 8,
  import_kwh: 2,
  export_kwh: 4,
  self_consumption_pct: 60,
  import_cost: 0.5,
  export_credit: 0.6,
  net_cost: -0.1,
  estimated_cost_without_solar: 2.2,
  savings: 2.3,
  currency: "GBP",
};

describe("buildSavingsInsights", () => {
  it("returns positive savings insight when summary shows savings", () => {
    const insights = buildSavingsInsights(baseMetrics, summary);
    expect(insights.some((i) => i.id === "savings-positive")).toBe(true);
  });

  it("warns when importing during sunny conditions", () => {
    const insights = buildSavingsInsights(
      { ...baseMetrics, grid_import_w: 800, grid_export_w: 0 },
      summary,
    );
    expect(insights.some((i) => i.id === "import-while-sunny")).toBe(true);
  });

  it("suggests cheap agile market only for Agile tariff users", () => {
    const agileInsights = buildSavingsInsights(
      { ...baseMetrics, grid_import_w: 500 },
      summary,
      { agilePricePence: 3, importRatePence: 22.4, tariffFamily: "AGILE" },
    );
    expect(agileInsights.some((i) => i.id === "cheap-agile-market")).toBe(true);

    const iogInsights = buildSavingsInsights(
      { ...baseMetrics, grid_import_w: 500 },
      summary,
      { agilePricePence: 3, importRatePence: 22.4, tariffFamily: "IOG" },
    );
    expect(iogInsights.some((i) => i.id === "cheap-agile-market")).toBe(false);
  });

  it("shows IOG tariff context when on intelligent go", () => {
    const insights = buildSavingsInsights(baseMetrics, summary, {
      importRatePence: 22.38,
      exportRatePence: 12,
      tariffFamily: "IOG",
    });
    expect(insights.some((i) => i.id === "iog-tariff-context")).toBe(true);
  });

  it("warns that export earns less than import when exporting on IOG", () => {
    const insights = buildSavingsInsights(
      { ...baseMetrics, grid_export_w: 1500 },
      summary,
      { importRatePence: 22.4, exportRatePence: 12, tariffFamily: "IOG" },
    );
    expect(insights.some((i) => i.id === "export-vs-import")).toBe(true);
  });

  it("always returns at least one insight", () => {
    const insights = buildSavingsInsights(baseMetrics, null);
    expect(insights.length).toBeGreaterThan(0);
  });
});
