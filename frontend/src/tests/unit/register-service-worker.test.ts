import { afterEach, describe, expect, it, vi } from "vitest";

import { registerServiceWorker } from "@/lib/register-service-worker";

describe("registerServiceWorker", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("no-ops when service workers are unavailable", () => {
    expect(() => registerServiceWorker()).not.toThrow();
  });

  it("registers with updateViaCache none", async () => {
    const update = vi.fn().mockResolvedValue(undefined);
    const register = vi.fn().mockResolvedValue({
      installing: null,
      waiting: null,
      addEventListener: vi.fn(),
      update,
    });

    vi.stubGlobal("navigator", {
      serviceWorker: {
        controller: null,
        register,
        addEventListener: vi.fn(),
      },
    });
    vi.stubGlobal("document", {
      addEventListener: vi.fn(),
    });
    vi.stubGlobal("window", {
      setInterval: vi.fn(),
      location: { reload: vi.fn() },
    });

    registerServiceWorker();

    expect(register).toHaveBeenCalledWith("/sw.js", {
      scope: "/",
      updateViaCache: "none",
    });
  });
});
