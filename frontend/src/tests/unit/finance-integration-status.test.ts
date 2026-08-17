import { describe, expect, it } from "vitest";

import { integrationConnectionLabel } from "@/lib/finance-schemas";

describe("integrationConnectionLabel", () => {
  it("maps hosted connection states", () => {
    expect(integrationConnectionLabel("active", true)).toBe("Active");
    expect(integrationConnectionLabel("key_saved", true)).toBe("Key saved");
    expect(integrationConnectionLabel("not_connected", false)).toBe("Not connected");
  });

  it("falls back when the API omits connection_state", () => {
    expect(integrationConnectionLabel(undefined, true)).toBe("Configured");
    expect(integrationConnectionLabel(undefined, false)).toBe("Not configured");
  });
});
