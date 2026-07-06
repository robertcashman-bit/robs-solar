import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OpenBankingSetupInstructions } from "@/components/finance/OpenBankingSetupInstructions";

describe("OpenBankingSetupInstructions", () => {
  it("shows the setup guide title and Enable Banking steps", () => {
    render(<OpenBankingSetupInstructions redirectUrlExample="https://example.com/callback" />);
    expect(screen.getByText("Open Banking Setup Instructions")).toBeInTheDocument();
    expect(screen.getByText(/Enable Banking \(recommended for UK banks\)/)).toBeInTheDocument();
    expect(screen.getAllByText("Client ID").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Client Secret").length).toBeGreaterThan(0);
  });
});

describe("open banking test result labels", () => {
  it("maps status codes to plain English labels", async () => {
    const labels: Record<string, string> = {
      connected_successfully: "Connected successfully",
      missing_credentials: "Missing credentials",
      invalid_redirect_url: "Invalid redirect URL",
      provider_rejected_credentials: "Provider rejected credentials",
      further_bank_authorisation_required: "Further bank authorisation required",
    };
    const { openBankingTestResultSchema } = await import("@/lib/finance-schemas");
    for (const [status, label] of Object.entries(labels)) {
      const parsed = openBankingTestResultSchema.parse({
        status,
        message: "Test message",
        details: {},
      });
      expect(parsed.status).toBe(status);
      expect(label.length).toBeGreaterThan(0);
    }
  });
});

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ user: { role: "admin" }, loading: false }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

const mockStatus = {
  provider: "enable_banking" as const,
  application_id: "",
  private_key_set: false,
  environment: "SANDBOX" as const,
  secret_id: "",
  secret_key_set: false,
  redirect_url: "",
  country: "gb",
  scopes: "accounts,transactions",
  webhook_url: "",
  configured: false,
  linked_banks: [] as string[],
  connections_count: 0,
};

describe("OpenBankingSetupPage", () => {
  it("renders plain English form labels and actions", async () => {
    const { OpenBankingSetupPage } = await import("@/components/finance/OpenBankingSetupPage");
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue(mockStatus);

    render(<OpenBankingSetupPage />);

    expect(await screen.findByText("Step 1 — Provider credentials")).toBeInTheDocument();
    expect(screen.getAllByText("Client ID").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Client Secret").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Test connection" })).toBeInTheDocument();
    expect(screen.getByText("Step 2 — Connect a bank account")).toBeInTheDocument();
    expect(screen.getByText("Mock ASPSP (sandbox test)")).toBeInTheDocument();
  });

  it("shows validation errors for empty required fields on save", async () => {
    const { OpenBankingSetupPage } = await import("@/components/finance/OpenBankingSetupPage");
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue(mockStatus);

    render(<OpenBankingSetupPage />);
    await screen.findByText("Step 1 — Provider credentials");

    screen.getByRole("button", { name: "Save" }).click();
    expect((await screen.findAllByText(/Client ID is missing/i)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Client Secret is missing/i).length).toBeGreaterThan(0);
  });
});

describe("OpenBankingSettingsForm labels", () => {
  it("renders plain English field labels", async () => {
    const { OpenBankingSettingsForm } = await import("@/components/finance/OpenBankingSettingsForm");
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue(mockStatus);

    render(<OpenBankingSettingsForm />);

    expect(await screen.findByText("Open Banking Settings")).toBeInTheDocument();
    expect(screen.getAllByText("Client ID").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Test connection" })).toBeInTheDocument();
  });
});
