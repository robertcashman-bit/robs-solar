import type { LiveMetrics } from "@/lib/schemas";

import { MetricCard } from "./MetricCard";
import { BoltIcon, BatteryIcon, GaugeIcon } from "@/components/shared/icons";

const BATTERY_KWH = 16.1;

function formatW(value: number) {
  return `${Math.round(value).toLocaleString()} W`;
}

function batteryEta(metrics: LiveMetrics): string | undefined {
  if (metrics.battery_power_w == null || Math.abs(metrics.battery_power_w) < 50) {
    return undefined;
  }
  const remainingKwh =
    metrics.battery_power_w > 0
      ? (metrics.battery_soc_pct / 100) * BATTERY_KWH
      : ((100 - metrics.battery_soc_pct) / 100) * BATTERY_KWH;
  const hours = remainingKwh / (Math.abs(metrics.battery_power_w) / 1000);
  if (!Number.isFinite(hours) || hours <= 0) {
    return undefined;
  }
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  return metrics.battery_power_w > 0 ? `Empty in ~${h}h ${m}m` : `Full in ~${h}h ${m}m`;
}

type LiveDetailCardsProps = {
  metrics: LiveMetrics;
};

export function LiveDetailCards({ metrics }: LiveDetailCardsProps) {
  const hasSplit = metrics.pv1_power_w != null && metrics.pv2_power_w != null;
  const eta = batteryEta(metrics);

  return (
    <section aria-label="Live detail metrics" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <MetricCard
        label={hasSplit ? "Solar PV1 / PV2" : "Solar generation"}
        value={
          hasSplit
            ? `${formatW(metrics.pv1_power_w!)} / ${formatW(metrics.pv2_power_w!)}`
            : formatW(metrics.pv_power_w)
        }
        hint={hasSplit ? `Total ${formatW(metrics.pv_power_w)}` : undefined}
        icon={<BoltIcon size={20} />}
        accent="pv"
      />
      <MetricCard
        label="Battery"
        value={`${metrics.battery_soc_pct.toFixed(1)}%`}
        hint={
          [
            metrics.battery_voltage_v != null ? `${metrics.battery_voltage_v.toFixed(1)} V` : null,
            metrics.battery_current_a != null ? `${metrics.battery_current_a.toFixed(1)} A` : null,
            metrics.battery_temp_c != null ? `${metrics.battery_temp_c.toFixed(0)}°C` : null,
            metrics.battery_soh_pct != null ? `SOH ${metrics.battery_soh_pct.toFixed(0)}%` : null,
            eta,
          ]
            .filter(Boolean)
            .join(" · ") || undefined
        }
        icon={<BatteryIcon size={20} />}
        accent="battery"
        progress={metrics.battery_soc_pct}
      />
      <MetricCard
        label="Grid"
        value={
          metrics.grid_export_w > 0
            ? `Export ${formatW(metrics.grid_export_w)}`
            : metrics.grid_import_w > 0
              ? `Import ${formatW(metrics.grid_import_w)}`
              : "0 W"
        }
        hint={
          [
            metrics.grid_voltage_v != null ? `${metrics.grid_voltage_v.toFixed(1)} V` : null,
            metrics.grid_frequency_hz != null ? `${metrics.grid_frequency_hz.toFixed(2)} Hz` : null,
          ]
            .filter(Boolean)
            .join(" · ") || undefined
        }
        icon={<GaugeIcon size={20} />}
        accent={metrics.grid_export_w > 0 ? "export" : "import"}
      />
      <MetricCard
        label="Inverter status"
        value={metrics.inverter_status.replaceAll("_", " ")}
        hint={metrics.inverter_status === "fault" ? "Check inverter diagnostics" : undefined}
        icon={<GaugeIcon size={20} />}
        accent={metrics.inverter_status === "fault" ? "import" : "battery"}
      />
    </section>
  );
}
