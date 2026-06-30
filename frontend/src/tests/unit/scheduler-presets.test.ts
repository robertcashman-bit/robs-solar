import { describe, expect, it } from "vitest";

import { slotPercent, STRATEGY_PRESETS } from "@/lib/scheduler-presets";

describe("scheduler-presets", () => {
  it("has strategy presets with descriptions", () => {
    expect(STRATEGY_PRESETS.length).toBeGreaterThanOrEqual(5);
    for (const preset of STRATEGY_PRESETS) {
      expect(preset.description.length).toBeGreaterThan(10);
      expect(preset.windows.length).toBeGreaterThan(0);
    }
  });

  it("computes slot percent from HH:MM", () => {
    expect(slotPercent("00:00")).toBe(0);
    expect(slotPercent("12:00")).toBe(50);
  });
});
