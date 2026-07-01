"use client";

type RemoteAccessPanelProps = {
  readOnly: boolean;
  liveWritesEnabled: boolean;
  adapterMode: string;
};

const HOSTED_URL = "https://robs-solar.vercel.app";

export function RemoteAccessPanel({
  readOnly,
  liveWritesEnabled,
  adapterMode,
}: RemoteAccessPanelProps) {
  const controlNote =
    readOnly || !liveWritesEnabled
      ? "Remote monitoring only — live inverter control is disabled on the hosted API."
      : "Live writes are enabled on the hosted API — use controls with care.";

  return (
    <section className="solar-card space-y-4">
      <div>
        <h3 className="solar-section-title">Remote access</h3>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Log in from anywhere using the hosted app. Your phone can install it as a home-screen app
          (PWA) for quick access.
        </p>
      </div>

      <dl className="grid gap-3 text-sm sm:grid-cols-2">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
          <dt className="text-xs font-medium uppercase tracking-wider text-[var(--muted)]">
            App URL
          </dt>
          <dd className="mt-1 font-medium">
            <a href={HOSTED_URL} className="text-[var(--accent)] hover:underline" target="_blank" rel="noreferrer">
              {HOSTED_URL}
            </a>
          </dd>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
          <dt className="text-xs font-medium uppercase tracking-wider text-[var(--muted)]">
            Adapter
          </dt>
          <dd className="mt-1 font-medium">{adapterMode}</dd>
        </div>
      </dl>

      <p className="rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] px-3 py-2 text-xs text-[var(--muted)]">
        {controlNote}
      </p>

      <div className="space-y-2 text-sm">
        <p className="font-medium">Install on your phone</p>
        <ul className="list-inside list-disc space-y-1 text-[var(--muted)]">
          <li>
            <strong className="text-[var(--foreground)]">iPhone (Safari):</strong> open the URL →
            Share → Add to Home Screen
          </li>
          <li>
            <strong className="text-[var(--foreground)]">Android (Chrome):</strong> open the URL →
            use the Install app banner or browser menu → Install app
          </li>
        </ul>
      </div>

      <div className="space-y-2 text-sm">
        <p className="font-medium">Hosted backend setup (one-time)</p>
        <ol className="list-inside list-decimal space-y-1 text-[var(--muted)]">
          <li>Deploy the Render blueprint from the repo README</li>
          <li>
            Run <code className="rounded bg-[var(--surface-sunken)] px-1">bash scripts/push-render-secrets.sh</code>{" "}
            with your Sunsynk credentials and strong passwords
          </li>
          <li>Set Vercel <code className="rounded bg-[var(--surface-sunken)] px-1">BACKEND_URL</code> to your Render API URL</li>
          <li>Redeploy with <code className="rounded bg-[var(--surface-sunken)] px-1">bash scripts/deploy-hosted.sh</code></li>
        </ol>
      </div>
    </section>
  );
}
