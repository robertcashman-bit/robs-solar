import {
  autoScheduleStatusSchema,
  controlWriteResultSchema,
  type AiProposedAction,
} from "@/lib/schemas";

/** Display-only helper for formatting historical apply responses (energy writes are UI-gated). */
export function summariseApplyResult(action: AiProposedAction, raw: unknown): string {
  if (action.kind === "set_auto_schedule") {
    const status = autoScheduleStatusSchema.parse(raw);
    if (status.last_run_message.trim()) {
      return status.last_run_message;
    }
    return `Auto-align ${status.enabled ? "on" : "off"}, SOC floor ${status.soc_floor_pct}%`;
  }

  const result = controlWriteResultSchema.parse(raw);
  const verified = result.verified
    ? "Confirmed on inverter"
    : result.verification_pending
      ? "Sent — awaiting confirmation"
      : result.message;
  return `Applied (audit #${result.audit_id}). ${verified}`;
}

export const ENERGY_WRITE_DISPLAY_ONLY_HINT =
  "Suggestion only — apply in Simple Solar or Sunsynk Connect. This app does not change inverter settings.";
