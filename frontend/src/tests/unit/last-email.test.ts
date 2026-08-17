import { afterEach, describe, expect, it } from "vitest";

import { lastEmailStorageKey, readLastEmail, rememberLastEmail } from "@/lib/last-email";

afterEach(() => {
  window.localStorage.clear();
});

describe("last email memory", () => {
  it("remembers and reads the last email", () => {
    rememberLastEmail("  Rob@Example.com ");
    expect(readLastEmail()).toBe("rob@example.com");
    expect(window.localStorage.getItem(lastEmailStorageKey())).toBe("rob@example.com");
  });

  it("promotes a legacy key", () => {
    window.localStorage.setItem("last-email", "legacy@example.com");
    expect(readLastEmail()).toBe("legacy@example.com");
    expect(window.localStorage.getItem(lastEmailStorageKey())).toBe("legacy@example.com");
  });
});
