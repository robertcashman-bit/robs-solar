import type { LoadDiagnostics, LoadFieldStatus } from "@/lib/schemas";
import { AlertIcon, CheckIcon, GaugeIcon } from "@/components/shared/icons";

function originBadge(origin: LoadFieldStatus["origin"] | LoadDiagnostics["measured_load_origin"]) {
  const styles: Record<string, string> = {
    live: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
    derived: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
    cached: "bg-sky-500/15 text-sky-700 dark:text-sky-300",
    missing: "bg-red-500/15 text-red-700 dark:text-red-300",
    unknown: "bg-slate-500/15 text-slate-700 dark:text-slate-300",
  };
  const labels: Record<string, string> = {
    live: "Live",
    derived: "Derived",
    cached: "Cached",
    missing: "Missing",
    unknown: "Unknown",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${styles[origin] ?? styles.unknown}`}
    >
      {labels[origin] ?? "Unknown"}
    </span>
  );
}

function formatValue(value: number | null | undefined, unit: string): string {
  if (value == null) {
    return "Unknown";
  }
  return `${Math.round(value).toLocaleString()} ${unit}`;
}

function FieldRow({ field }: { field: LoadFieldStatus }) {
  return (
    <tr className="border-t border-[var(--border)]">
      <td className="py-2 pr-4 font-medium">{field.label}</td>
      <td className="py-2 pr-4 tabular-nums">{formatValue(field.value, field.unit)}</td>
      <td className="py-2 pr-4">{originBadge(field.origin)}</td>
      <td className="py-2 pr-4 font-mono text-xs text-[var(--muted)]">
        {field.source_field ?? "—"}
      </td>
      <td className="py-2 text-xs text-[var(--muted)]">{field.note ?? "—"}</td>
    </tr>
  );
}

function agoLabel(seconds: number | null | undefined): string {
  if (seconds == null) {
    return "unknown age";
  }
  if (seconds < 1) {
    return "just now";
  }
  if (seconds < 60) {
    return `${Math.round(seconds)}s ago`;
  }
  return `${Math.round(seconds / 60)}m ago`;
}

const PHYSICAL_CHECKLIST = [
  "CT clamp fitted in the wrong place (e.g. on a sub-circuit, not the main incomer).",
  "CT clamp facing the wrong direction (reversed polarity can read as 0 or negative).",
  "Missing or disconnected load/CT sensor — no clamp physically wired to the Load CT input.",
  "Inverter configured as grid CT only, not load/house consumption CT.",
  "App/cloud showing only EPS/essential load, not whole-house load.",
  "Some circuits wired around the inverter's measured output (not on the monitored side).",
  "Split consumer unit where only some circuits are measured.",
  "Incorrect meter/CT ratio or settings in the inverter's meter configuration.",
  "The \"Meter\"/CT-enable setting disabled in inverter settings.",
  "Wrong work mode or system mode setting affecting what the cloud reports.",
  "Sunsynk cloud/API simply not exposing the desired load field for this account/plant.",
];

type LoadDiagnosticsPanelProps = {
  diagnostics: LoadDiagnostics | null;
  error?: string | null;
  loading?: boolean;
  onRefresh?: () => void;
};

export function LoadDiagnosticsPanel({
  diagnostics,
  error,
  loading,
  onRefresh,
}: LoadDiagnosticsPanelProps) {
  if (error) {
    return (
      <section role="alert" className="solar-card space-y-2 border-red-300/50 bg-red-50/50 dark:bg-red-950/20">
        <p className="font-medium text-red-800 dark:text-red-300">Failed to load diagnostics</p>
        <p className="text-sm text-red-700/90 dark:text-red-300/80">{error}</p>
      </section>
    );
  }

  if (!diagnostics) {
    return (
      <section className="solar-card text-sm text-[var(--muted)]" role="status">
        {loading ? "Loading diagnostics…" : "No diagnostics yet."}
      </section>
    );
  }

  const meterMissing = diagnostics.grid_meter_connected === false;
  const rawPayloadJson = diagnostics.raw_payload
    ? JSON.stringify(diagnostics.raw_payload, null, 2)
    : null;

  return (
    <div className="space-y-6">
      <section className="solar-card space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm text-[var(--muted)]">
            <GaugeIcon size={18} />
            <span>
              Adapter <strong className="text-[var(--foreground)]">{diagnostics.adapter_mode}</strong> ·
              Data source <strong className="text-[var(--foreground)]">{diagnostics.data_source}</strong>
            </span>
          </div>
          <div className="flex items-center gap-2">
            {originBadge(diagnostics.is_cached ? "cached" : "live")}
            <span className="text-xs text-[var(--muted)]">
              {diagnostics.is_cached ? "Cached snapshot" : "Live fetch"} ·{" "}
              {agoLabel(diagnostics.cache_age_seconds)}
            </span>
            {onRefresh ? (
              <button
                type="button"
                onClick={onRefresh}
                className="rounded-lg border border-[var(--border)] px-2 py-1 text-xs font-medium hover:bg-[var(--surface-sunken)]"
              >
                Refresh
              </button>
            ) : null}
          </div>
        </div>
        {meterMissing ? (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-lg border border-amber-300/50 bg-amber-50/60 px-3 py-2 text-sm text-amber-900 dark:border-amber-800/50 dark:bg-amber-950/30 dark:text-amber-200"
          >
            <AlertIcon size={16} className="mt-0.5 shrink-0" />
            <span>
              Sunsynk reports <code>existsMeter=false</code> for this plant — the cloud is not
              receiving a working grid/load CT reading. This is most likely a physical
              installation issue, not a bug in this app.
            </span>
          </div>
        ) : null}
      </section>

      <section className="solar-card space-y-3">
        <h3 className="text-base font-semibold">Measured Load vs Estimated Load</h3>
        <p className="text-sm text-[var(--muted)]">
          Measured Load is read directly from the inverter/cloud CT. Estimated Load is calculated
          from the power balance (PV + grid import − grid export + battery). These are always kept
          separate — Estimated Load is never silently substituted for Measured Load.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-xl border border-[var(--border)] p-4">
            <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Measured Load</p>
            <p className="mt-1 text-2xl font-bold tabular-nums">
              {formatValue(diagnostics.measured_load_w, "W")}
            </p>
            <div className="mt-2">{originBadge(diagnostics.measured_load_origin)}</div>
          </div>
          <div className="rounded-xl border border-[var(--border)] p-4">
            <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Estimated Load</p>
            <p className="mt-1 text-2xl font-bold tabular-nums">
              {formatValue(diagnostics.estimated_load_w, "W")}
            </p>
            <p className="mt-2 font-mono text-xs text-[var(--muted)]">
              {diagnostics.estimated_load_formula}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <CheckIcon size={16} className="text-emerald-600" />
          <span>
            App is currently showing{" "}
            <strong>{formatValue(diagnostics.house_load_w, "W")}</strong> as Load, source{" "}
            <code className="rounded bg-[var(--surface-sunken)] px-1">
              {diagnostics.house_load_source}
            </code>
            .
          </span>
        </div>
      </section>

      <section className="solar-card space-y-3">
        <h3 className="text-base font-semibold">Power-flow fields</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wide text-[var(--muted)]">
                <th className="pb-2 pr-4">Field</th>
                <th className="pb-2 pr-4">Value</th>
                <th className="pb-2 pr-4">Source</th>
                <th className="pb-2 pr-4">API field</th>
                <th className="pb-2">Note</th>
              </tr>
            </thead>
            <tbody>
              <FieldRow field={diagnostics.pv} />
              <FieldRow field={diagnostics.battery} />
              <FieldRow field={diagnostics.grid_import} />
              <FieldRow field={diagnostics.grid_export} />
            </tbody>
          </table>
        </div>
      </section>

      <section className="solar-card space-y-3">
        <h3 className="text-base font-semibold">Raw payload</h3>
        {diagnostics.raw_payload_note ? (
          <p className="text-sm text-[var(--muted)]">{diagnostics.raw_payload_note}</p>
        ) : null}
        {rawPayloadJson ? (
          <>
            <p className="text-xs text-[var(--muted)]">
              Captured at{" "}
              {diagnostics.raw_payload_captured_at
                ? new Date(diagnostics.raw_payload_captured_at).toLocaleString()
                : "unknown time"}
              , before any parsing/transformation.
            </p>
            <pre className="max-h-96 overflow-auto rounded-lg bg-[var(--surface-sunken)] p-3 text-xs">
              {rawPayloadJson}
            </pre>
          </>
        ) : null}
      </section>

      <details className="solar-card group">
        <summary className="cursor-pointer text-sm font-semibold">
          Physical / installation checklist (if Load looks wrong on every app, not just this one)
        </summary>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-[var(--muted)]">
          {PHYSICAL_CHECKLIST.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </details>
    </div>
  );
}
