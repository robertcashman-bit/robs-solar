"use client";

import { useState } from "react";

import { INSTALLER_REQUEST_EMAIL } from "@/lib/installer-request";

type InstallerAccessPanelProps = {
  plantName?: string;
  installerName?: string;
};

export function InstallerAccessPanel({
  plantName = "Greenacre",
  installerName = "The Solar Co. (George / Mark Evans)",
}: InstallerAccessPanelProps) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(INSTALLER_REQUEST_EMAIL);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <section className="solar-card space-y-4" aria-label="Installer access request">
      <div>
        <h3 className="solar-section-title">Unlock inverter control</h3>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Your Sunsynk account can read {plantName} but cannot change settings. Simple Solar and
          other apps use the same account — changes you make there may save locally but are rejected
          by Sunsynk until {installerName} grants full control.
        </p>
      </div>

      <ul className="list-disc space-y-1 pl-5 text-sm text-[var(--muted)]">
        <li>No local Modbus dongle was found on your home network.</li>
        <li>Cloud writes return &quot;No Permissions&quot; on your current plant share.</li>
        <li>Rob&apos;s Solar will enable controls automatically once write access is granted.</li>
      </ul>

      <details className="rounded-xl border border-[var(--border)] bg-[var(--surface-sunken)] p-4">
        <summary className="cursor-pointer text-sm font-medium">
          Message to send your installer
        </summary>
        <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap text-xs text-[var(--muted)]">
          {INSTALLER_REQUEST_EMAIL}
        </pre>
      </details>

      <div className="flex flex-wrap gap-3">
        <button type="button" className="solar-btn-primary" onClick={() => void copy()}>
          {copied ? "Copied" : "Copy installer message"}
        </button>
        <a
          className="solar-btn-ghost inline-flex items-center"
          href="mailto:george.penny@thesolarco.uk,mark.evans@thesolarco.uk?subject=Request%20full%20Sunsynk%20control%20-%20Greenacre"
        >
          Open email draft
        </a>
      </div>
    </section>
  );
}
