import { describe, expect, it } from "vitest";

import { summariseApplyResult } from "@/lib/ai-apply";
import type { AiProposedAction } from "@/lib/schemas";

const autoScheduleAction: AiProposedAction = {
  kind: "set_auto_schedule",
  endpoint: "/controls/auto-schedule",
  summary: "Enable auto-align",
  reason: "Prevent expensive grid import",
  body: { enabled: true, soc_floor_pct: 20 },
};

const touBandsAction: AiProposedAction = {
  kind: "set_tou_bands",
  endpoint: "/controls/tou-bands",
  summary: "Update charge schedule",
  reason: "Align bands to cheap windows",
  body: { bands: [] },
};

describe("summariseApplyResult", () => {
  it("returns last_run_message for set_auto_schedule responses", () => {
    const message = summariseApplyResult(autoScheduleAction, {
      enabled: true,
      soc_floor_pct: 20,
      last_run_message: "Schedule updated (audit #42)",
      next_cheap_windows: [],
      computed_bands: [],
    });
    expect(message).toBe("Schedule updated (audit #42)");
  });

  it("falls back to enabled/soc floor when last_run_message is empty", () => {
    const message = summariseApplyResult(autoScheduleAction, {
      enabled: false,
      soc_floor_pct: 25,
      last_run_message: "",
      next_cheap_windows: [],
      computed_bands: [],
    });
    expect(message).toBe("Auto-align off, SOC floor 25%");
  });

  it("returns audit and verification text for control write responses", () => {
    const message = summariseApplyResult(touBandsAction, {
      success: true,
      message: "Bands updated",
      audit_id: 7,
      verified: true,
    });
    expect(message).toBe("Applied (audit #7). Confirmed on inverter");
  });

  it("throws when the response does not match the expected schema", () => {
    expect(() => summariseApplyResult(touBandsAction, { enabled: true })).toThrow();
  });
});
