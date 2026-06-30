"use client";

import { useState } from "react";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import {
  notificationCategoryToggleSchema,
  type NotificationSettingsStatus,
} from "@/lib/schemas";

type NotificationSettingsFormProps = {
  initial: NotificationSettingsStatus;
  onSubmit: (settings: Record<string, unknown>) => Promise<void>;
};

const CATEGORY_LABELS: Record<string, string> = {
  soc_low: "Battery SOC low",
  soc_high: "Battery SOC high",
  import_high: "High grid import",
  offline: "Inverter offline",
  negative_price: "Negative Agile price",
  price_spike: "Agile price spike",
  dispatch_available: "IOG dispatch available",
  export_price_high: "High export rate",
  soc_low_before_offpeak: "SOC low before off-peak",
  inverter_fault: "Inverter fault",
};

export function NotificationSettingsForm({ initial, onSubmit }: NotificationSettingsFormProps) {
  const [webhookUrl, setWebhookUrl] = useState("");
  const [smtpHost, setSmtpHost] = useState("");
  const [smtpPort, setSmtpPort] = useState("587");
  const [smtpUser, setSmtpUser] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [emailTo, setEmailTo] = useState(initial.email_to);
  const [exportThreshold, setExportThreshold] = useState(String(initial.export_price_threshold_pence));
  const [categories, setCategories] = useState(initial.categories);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const parsedCategories = notificationCategoryToggleSchema.parse(categories);
      await onSubmit({
        webhook_url: webhookUrl,
        smtp_host: smtpHost,
        smtp_port: Number(smtpPort) || 587,
        smtp_user: smtpUser,
        smtp_password: smtpPassword,
        email_to: emailTo,
        export_price_threshold_pence: Number(exportThreshold) || 20,
        categories: parsedCategories,
      });
      setSuccess("Notification settings saved");
      setConfirmOpen(false);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Save failed");
      setConfirmOpen(false);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="solar-card space-y-4">
      <div>
        <h3 className="solar-section-title">Alert notifications</h3>
        <p className="text-sm text-[var(--muted)]">
          Webhook and optional SMTP email when alert rules fire.
          {initial.webhook_url_set ? " Webhook configured." : ""}
          {initial.smtp_configured ? " SMTP configured." : ""}
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="text-[var(--muted)]">Webhook URL</span>
          <input
            className="solar-input mt-1 w-full"
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
            placeholder={initial.webhook_url_set ? "Leave blank to keep existing" : "https://…"}
          />
        </label>
        <label className="block text-sm">
          <span className="text-[var(--muted)]">Email to</span>
          <input
            className="solar-input mt-1 w-full"
            type="email"
            value={emailTo}
            onChange={(e) => setEmailTo(e.target.value)}
          />
        </label>
        <label className="block text-sm">
          <span className="text-[var(--muted)]">SMTP host</span>
          <input className="solar-input mt-1 w-full" value={smtpHost} onChange={(e) => setSmtpHost(e.target.value)} />
        </label>
        <label className="block text-sm">
          <span className="text-[var(--muted)]">SMTP port</span>
          <input className="solar-input mt-1 w-full" value={smtpPort} onChange={(e) => setSmtpPort(e.target.value)} />
        </label>
        <label className="block text-sm">
          <span className="text-[var(--muted)]">SMTP user</span>
          <input className="solar-input mt-1 w-full" value={smtpUser} onChange={(e) => setSmtpUser(e.target.value)} />
        </label>
        <label className="block text-sm">
          <span className="text-[var(--muted)]">SMTP password</span>
          <input
            className="solar-input mt-1 w-full"
            type="password"
            value={smtpPassword}
            onChange={(e) => setSmtpPassword(e.target.value)}
            placeholder="Leave blank to keep existing"
          />
        </label>
        <label className="block text-sm sm:col-span-2">
          <span className="text-[var(--muted)]">Export rate alert threshold (p/kWh)</span>
          <input
            className="solar-input mt-1 w-full max-w-xs"
            value={exportThreshold}
            onChange={(e) => setExportThreshold(e.target.value)}
          />
        </label>
      </div>
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">Alert categories</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
            <label key={key} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={categories[key as keyof typeof categories]}
                onChange={(e) =>
                  setCategories((prev) => ({ ...prev, [key]: e.target.checked }))
                }
              />
              {label}
            </label>
          ))}
        </div>
      </fieldset>
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
      {success ? <p className="text-sm text-emerald-600">{success}</p> : null}
      <button type="button" className="solar-btn-primary" onClick={() => setConfirmOpen(true)}>
        Save notifications
      </button>
      <ConfirmDialog
        open={confirmOpen}
        title="Save notification settings?"
        description="SMTP credentials are stored in the app database (same as Octopus API key)."
        confirmLabel={submitting ? "Saving…" : "Save"}
        onConfirm={() => void handleSubmit()}
        onCancel={() => setConfirmOpen(false)}
      />
    </section>
  );
}
