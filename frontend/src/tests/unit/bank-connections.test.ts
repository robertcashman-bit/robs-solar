import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api-client";
import { mapOpenBankingConnectError } from "@/lib/bank-connections";
import { openBankingConfigStatusSchema } from "@/lib/finance-schemas";

describe("mapOpenBankingConnectError", () => {
  it("maps inactive application errors to activation guidance", () => {
    const err = new ApiError(
      "Your provider accepted the credentials but the app is not fully active yet.",
      400,
      "further_bank_authorisation_required",
    );
    expect(mapOpenBankingConnectError(err)).toMatch(/not active yet/i);
    expect(mapOpenBankingConnectError(err)).toMatch(/Enable Banking Control Panel/i);
  });

  it("passes through other API errors", () => {
    const err = new ApiError("Invalid redirect URL", 400, "invalid_redirect_url");
    expect(mapOpenBankingConnectError(err)).toBe("Invalid redirect URL");
  });
});

describe("openBankingConfigStatusSchema", () => {
  it("parses provider readiness fields", () => {
    const parsed = openBankingConfigStatusSchema.parse({
      provider: "enable_banking",
      application_id: "app-123",
      private_key_set: true,
      environment: "PRODUCTION",
      secret_id: "",
      secret_key_set: false,
      redirect_url: "https://example.com/open-banking/callback",
      configured: true,
      provider_ready: false,
      readiness_message: "App is not active",
      readiness_status: "further_bank_authorisation_required",
      linked_banks: [],
      connections_count: 0,
    });
    expect(parsed.provider_ready).toBe(false);
    expect(parsed.readiness_status).toBe("further_bank_authorisation_required");
  });
});
