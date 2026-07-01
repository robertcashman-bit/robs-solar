"use client";

import type { ReactNode } from "react";

import type { LiveMetrics } from "@/lib/schemas";
import {
  BoltIcon,
  BatteryIcon,
  HomeIcon,
  ArrowDownIcon,
  ArrowUpIcon,
  GaugeIcon,
} from "@/components/shared/icons";

type EnergyFlowProps = {
  metrics: LiveMetrics;
};

function formatW(value: number) {
  return `${Math.round(Math.abs(value)).toLocaleString()} W`;
}

const FLOW_THRESHOLD = 50;

type Anchor = { x: number; y: number };

function resolveBatteryPower(metrics: LiveMetrics): number {
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

function resolveHouseLoad(metrics: LiveMetrics, batteryPower: number): number {
  if (metrics.house_load_w > FLOW_THRESHOLD) {
    return metrics.house_load_w;
  }
  const derived =
    metrics.pv_power_w + metrics.grid_import_w - metrics.grid_export_w + batteryPower;
  return derived > FLOW_THRESHOLD ? derived : metrics.house_load_w;
}

/** Animated connector drawn behind the nodes. Coordinates are in percent. */
function FlowConnector({
  from,
  to,
  active,
  color,
  strength,
}: {
  from: Anchor;
  to: Anchor;
  active: boolean;
  color: string;
  strength: number;
}) {
  const width = 2 + Math.min(4, strength * 4);
  return (
    <g>
      <line
        x1={from.x}
        y1={from.y}
        x2={to.x}
        y2={to.y}
        stroke="var(--border-strong)"
        strokeWidth={1.5}
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
      {active ? (
        <line
          x1={from.x}
          y1={from.y}
          x2={to.x}
          y2={to.y}
          stroke={color}
          strokeWidth={width}
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
          className="energy-flow-line"
          style={{ filter: `drop-shadow(0 0 4px ${color}88)` }}
        />
      ) : null}
    </g>
  );
}

function FlowNode({
  icon,
  label,
  value,
  sub,
  accentVar,
  active,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  sub?: string;
  accentVar: string;
  active: boolean;
}) {
  return (
    <div
      className="relative flex flex-col items-center gap-1.5 rounded-2xl border bg-[var(--surface-elevated)] px-3 py-3 text-center backdrop-blur-sm transition-all duration-300"
      style={{
        borderColor: active ? accentVar : "var(--border)",
        boxShadow: active ? `0 0 0 1px ${accentVar}, 0 8px 24px -12px ${accentVar}` : "var(--shadow-sm)",
      }}
    >
      <span
        className="flex h-9 w-9 items-center justify-center rounded-xl transition-colors"
        style={{
          color: active ? "#fff" : accentVar,
          background: active ? accentVar : `color-mix(in srgb, ${accentVar} 14%, transparent)`,
        }}
      >
        {icon}
      </span>
      <span className="text-[0.7rem] font-medium uppercase tracking-wide text-[var(--muted)]">{label}</span>
      <span className="text-base font-bold leading-none tracking-tight tabular-nums">{value}</span>
      {sub ? <span className="text-[0.7rem] text-[var(--muted)]">{sub}</span> : null}
    </div>
  );
}

export function EnergyFlow({ metrics }: EnergyFlowProps) {
  const pvActive = metrics.pv_power_w > FLOW_THRESHOLD;
  const importActive = metrics.grid_import_w > FLOW_THRESHOLD;
  const exportActive = metrics.grid_export_w > FLOW_THRESHOLD;

  const batteryPower = resolveBatteryPower(metrics);
  const houseLoadW = resolveHouseLoad(metrics, batteryPower);
  const charging = batteryPower < -FLOW_THRESHOLD;
  const discharging = batteryPower > FLOW_THRESHOLD;
  const batteryFlowSub =
    charging || discharging
      ? `${formatW(batteryPower)} ${charging ? "Charging" : "Discharging"}`
      : "Idle";

  const loadActive = houseLoadW > FLOW_THRESHOLD;
  const inverterOutputW = houseLoadW + metrics.grid_export_w;

  const peak = Math.max(
    metrics.pv_power_w,
    houseLoadW,
    metrics.grid_import_w,
    metrics.grid_export_w,
    Math.abs(batteryPower),
    inverterOutputW,
    1,
  );

  const hub: Anchor = { x: 50, y: 50 };
  const solar: Anchor = { x: 50, y: 15 };
  const home: Anchor = { x: 84, y: 50 };
  const battery: Anchor = { x: 50, y: 85 };
  const grid: Anchor = { x: 16, y: 50 };

  const pvColor = "var(--accent-pv)";
  const loadColor = "var(--accent-load)";
  const batteryColor = "var(--accent-battery)";
  const importColor = "var(--accent-import)";
  const exportColor = "var(--accent-export)";

  return (
    <section aria-label="Energy flow" className="solar-card overflow-hidden">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="solar-section-title">Energy flow</h2>
          <p className="mt-0.5 text-sm text-[var(--muted)]">
            Live power routed through your inverter.
          </p>
        </div>
        <span className="solar-status-pill text-[var(--accent-battery)]">
          <span className="solar-status-dot solar-dot-live" style={{ background: "currentColor" }} />
          Live
        </span>
      </div>

      <div className="relative mt-4 aspect-[4/3] w-full sm:aspect-[16/9]">
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          className="absolute inset-0 h-full w-full"
          aria-hidden="true"
        >
          <FlowConnector
            from={solar}
            to={hub}
            active={pvActive}
            color={pvColor}
            strength={metrics.pv_power_w / peak}
          />
          <FlowConnector
            from={hub}
            to={home}
            active={loadActive}
            color={loadColor}
            strength={houseLoadW / peak}
          />
          <FlowConnector
            from={charging ? hub : battery}
            to={charging ? battery : hub}
            active={charging || discharging}
            color={batteryColor}
            strength={Math.abs(batteryPower) / peak}
          />
          <FlowConnector
            from={exportActive ? hub : grid}
            to={exportActive ? grid : hub}
            active={importActive || exportActive}
            color={exportActive ? exportColor : importColor}
            strength={Math.max(metrics.grid_import_w, metrics.grid_export_w) / peak}
          />
        </svg>

        <div className="absolute inset-0 grid grid-cols-3 grid-rows-3 gap-1">
          <div className="col-start-2 row-start-1 flex items-center justify-center">
            <FlowNode
              icon={<BoltIcon size={18} />}
              label="Solar"
              value={formatW(metrics.pv_power_w)}
              sub={
                metrics.pv1_power_w != null && metrics.pv2_power_w != null
                  ? `PV1 ${formatW(metrics.pv1_power_w)} · PV2 ${formatW(metrics.pv2_power_w)}`
                  : undefined
              }
              accentVar={pvColor}
              active={pvActive}
            />
          </div>
          <div className="col-start-1 row-start-2 flex items-center justify-center">
            <FlowNode
              icon={importActive ? <ArrowDownIcon size={18} /> : <ArrowUpIcon size={18} />}
              label="Grid"
              value={
                exportActive
                  ? formatW(metrics.grid_export_w)
                  : importActive
                    ? formatW(metrics.grid_import_w)
                    : "0 W"
              }
              sub={exportActive ? "Exporting" : importActive ? "Importing" : "Idle"}
              accentVar={exportActive ? exportColor : importColor}
              active={importActive || exportActive}
            />
          </div>

          <div className="col-start-2 row-start-2 flex items-center justify-center">
            <div className="relative flex aspect-square w-[78%] max-w-[128px] items-center justify-center">
              <span
                className="absolute inset-0 rounded-full"
                style={{
                  background:
                    "radial-gradient(circle, color-mix(in srgb, var(--accent-inverter) 45%, transparent), transparent 70%)",
                  filter: "blur(14px)",
                  animation: "hub-glow 3.2s ease-in-out infinite",
                }}
              />
              <div
                className="relative flex aspect-square w-full flex-col items-center justify-center rounded-full border px-1 text-center"
                style={{
                  borderColor: "var(--border-strong)",
                  background:
                    "radial-gradient(circle at 50% 30%, color-mix(in srgb, var(--accent-inverter) 22%, transparent), var(--surface-solid) 72%)",
                  boxShadow: "var(--shadow-lg)",
                }}
              >
                <span className="text-[var(--accent-inverter)]">
                  <GaugeIcon size={22} />
                </span>
                <span className="mt-1 text-[0.65rem] font-medium uppercase tracking-wide text-[var(--muted)]">
                  Inverter
                </span>
                <span className="text-sm font-bold tabular-nums leading-tight">
                  {formatW(inverterOutputW)}
                </span>
                <span className="px-1 text-[0.65rem] font-medium capitalize leading-tight text-[var(--muted)]">
                  {metrics.inverter_mode.replaceAll("_", " ")}
                </span>
              </div>
            </div>
          </div>

          <div className="col-start-3 row-start-2 flex items-center justify-center">
            <FlowNode
              icon={<HomeIcon size={18} />}
              label="Home"
              value={formatW(houseLoadW)}
              accentVar={loadColor}
              active={loadActive}
            />
          </div>
          <div className="col-start-2 row-start-3 flex items-center justify-center">
            <FlowNode
              icon={<BatteryIcon size={18} />}
              label="Battery"
              value={`${metrics.battery_soc_pct.toFixed(1)}%`}
              sub={batteryFlowSub}
              accentVar={batteryColor}
              active={charging || discharging}
            />
          </div>
        </div>
      </div>
    </section>
  );
}
