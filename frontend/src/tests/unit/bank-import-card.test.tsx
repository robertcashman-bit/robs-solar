import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BankImportCard } from "@/components/finance/BankImportCard";
import { apiClient } from "@/lib/api-client";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { username: "admin", role: "admin" },
    loading: false,
  }),
}));

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const disconnected = {
  client_id: "tl-client",
  client_secret_set: true,
  redirect_uri: "http://127.0.0.1:8000/finance/integrations/open-banking/callback",
  environment: "sandbox",
  configured: true,
  connected: false,
  last_sync_at: null,
};

const connected = {
  ...disconnected,
  connected: true,
  last_sync_at: "2026-08-14T10:00:00+00:00",
};

describe("BankImportCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.sessionStorage.clear();
  });

  it("hides the TrueLayer import card when that feed is not configured", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      ...disconnected,
      configured: false,
      client_id: "",
      client_secret_set: false,
    });
    const { container } = render(<BankImportCard />);
    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalled();
    });
    expect(screen.queryByText(/Log in and pull everything in/i)).not.toBeInTheDocument();
    expect(container).toBeEmptyDOMElement();
  });

  it("starts bank login when the bank is not connected", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.get).mockImplementation(async (path: string) => {
      if (path.includes("/authorize")) {
        return { authorize_url: "https://auth.truelayer-sandbox.com/?client_id=tl-client" };
      }
      return disconnected;
    });

    render(<BankImportCard />);
    const button = await screen.findByRole("button", { name: "Log in to your bank and import" });
    await user.click(button);
    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith("/finance/integrations/open-banking/authorize");
    });
  });

  it("pulls accounts and Funding Circle when already connected", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.get).mockResolvedValue(connected);
    vi.mocked(apiClient.post).mockResolvedValue({
      accounts_synced: 2,
      message: "Synced 2 Open Banking account(s). Imported from the connected bank login",
      funding_circle_imported: true,
      funding_circle_message: "Imported from the connected bank login",
    });

    render(<BankImportCard />);
    const button = await screen.findByRole("button", { name: "Pull latest from your bank" });
    await user.click(button);
    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/finance/integrations/open-banking/sync");
    });
    expect(
      await screen.findByText("Synced 2 Open Banking account(s). Imported from the connected bank login"),
    ).toBeInTheDocument();
  });
});
