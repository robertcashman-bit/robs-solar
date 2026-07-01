type LiveDataRequiredPanelProps = {
  adapterMode?: string;
};

/** Shown instead of live watts/savings when the backend is not on a real inverter adapter. */
export function LiveDataRequiredPanel({ adapterMode }: LiveDataRequiredPanelProps) {
  return (
    <section
      role="alert"
      className="solar-card space-y-3 border-amber-300/50 bg-amber-50/50 dark:bg-amber-950/20"
    >
      <h2 className="text-lg font-semibold text-amber-950 dark:text-amber-100">
        Live inverter data required
      </h2>
      <p className="text-sm text-amber-900/90 dark:text-amber-200/90">
        This dashboard only shows readings from your real Sunsynk system. Simulated adapter mode is
        enabled{adapterMode ? ` (${adapterMode})` : ""}, so watts, savings, and charts are hidden
        to avoid misleading figures.
      </p>
      <p className="text-sm text-[var(--muted)]">
        Set{" "}
        <code className="rounded bg-[var(--surface-sunken)] px-1">ADAPTER_MODE=sunsynk_connect</code>{" "}
        in <code className="rounded bg-[var(--surface-sunken)] px-1">backend/.env</code>, configure
        your Sunsynk credentials, and restart the backend.
      </p>
    </section>
  );
}
