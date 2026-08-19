import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { QuickFileSettingsPanel } from "@/components/settings/QuickFileSettingsPanel";
import {
  quickFileConfigStatusSchema,
  quickFileSyncResultSchema,
} from "@/lib/finance-schemas";

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock("@/lib/auth-context", () => {
  const user = { id: "1", role: "admin" };
  return {
    useAuth: () => ({ user, loading: false }),
  };
});

vi.mock("@/lib/finance-events", () => ({
  notifyFinanceChanged: vi.fn(),
}));

import { apiClient } from "@/lib/api-client";

describe("quickFileConfigStatusSchema", () => {
  it("accepts extra fields and marks connected when configured", () => {
    const parsed = quickFileConfigStatusSchema.parse({
      account_number: "6111393904",
      api_key_set: true,
      application_id: "app-id",
      configured: true,
      last_sync_at: "2026-08-18T10:00:00Z",
      budget_account_external_ids: [],
      future_extra: "ignored",
    });
    expect(parsed.configured).toBe(true);
    expect(parsed.connected).toBe(true);
    expect(parsed.budget_account_external_ids).toEqual([]);
    expect(parsed.last_sync_at).toBe("2026-08-18T10:00:00Z");
  });

  it("defaults connected from configured when omitted", () => {
    const parsed = quickFileConfigStatusSchema.parse({
      account_number: "1",
      api_key_set: true,
      application_id: "a",
      configured: true,
    });
    expect(parsed.connected).toBe(true);
  });
});

describe("quickFileSyncResultSchema", () => {
  it("accepts imported/duplicates/rejected extras", () => {
    const parsed = quickFileSyncResultSchema.parse({
      accounts_synced: 2,
      debtors_gbp: 100,
      message: "ok",
      imported: 5,
      duplicates: 1,
      rejected: 0,
      mystery: true,
    });
    expect(parsed.imported).toBe(5);
    expect(parsed.duplicates).toBe(1);
    expect(parsed.rejected).toBe(0);
  });
});

describe("QuickFileSettingsPanel", () => {
  beforeEach(() => {
    vi.mocked(apiClient.get).mockReset();
    vi.mocked(apiClient.put).mockReset();
    vi.mocked(apiClient.post).mockReset();
  });

  it("shows Connected when status.configured is true, including extra fields", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      account_number: "6111393904",
      api_key_set: true,
      application_id: "app-id",
      configured: true,
      connected: true,
      last_sync_at: "2026-08-18T12:00:00Z",
      budget_account_external_ids: [],
    });

    render(<QuickFileSettingsPanel />);

    expect(await screen.findByText("Connected")).toBeInTheDocument();
    expect(screen.queryByText("Not configured")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sync now/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Test$/i })).toBeInTheDocument();
    expect(screen.queryByText("Account number")).not.toBeInTheDocument();
  });

  it("does not show Not configured when the status call fails", async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error("network down"));

    render(<QuickFileSettingsPanel />);

    expect(await screen.findByText("Status unavailable")).toBeInTheDocument();
    expect(screen.queryByText("Not configured")).not.toBeInTheDocument();
    expect(screen.getByText(/network down/i)).toBeInTheDocument();
  });

  it("hides credential form behind Update keys when connected", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.get).mockResolvedValue({
      account_number: "6111393904",
      api_key_set: true,
      application_id: "app-id",
      configured: true,
      connected: true,
      last_sync_at: null,
      budget_account_external_ids: [],
    });

    render(<QuickFileSettingsPanel />);
    const updateKeys = await screen.findByRole("button", { name: /Update keys/i });
    expect(screen.queryByText("Account number")).not.toBeInTheDocument();

    await user.click(updateKeys);
    expect(await screen.findByText("Account number")).toBeInTheDocument();
  });

  it("shows quota banner while staying Connected", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      account_number: "6111393904",
      api_key_set: true,
      application_id: "app-id",
      configured: true,
      connected: true,
      last_sync_at: "2026-08-18T12:00:00Z",
      budget_account_external_ids: [],
      last_error: "API request limit exceeded (1000)",
      quota_exhausted_at: "2026-08-18T17:00:00Z",
    });

    render(<QuickFileSettingsPanel />);
    expect(await screen.findByText(/Connected · quota paused/i)).toBeInTheDocument();
    expect(screen.getByText(/retry after midnight UTC/i)).toBeInTheDocument();
    expect(screen.queryByText("Not configured")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Import full history/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Sync now/i })).not.toBeDisabled();
  });

  it("never renders Not configured for a configured:true payload", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      account_number: "",
      api_key_set: true,
      application_id: "",
      configured: true,
      budget_account_external_ids: ["ext-1"],
    });

    render(<QuickFileSettingsPanel />);
    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });
    expect(screen.queryByText("Not configured")).not.toBeInTheDocument();
  });

  it("Sync now posts without force_full; Import full history posts with force_full=true", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.get).mockResolvedValue({
      account_number: "6111393904",
      api_key_set: true,
      application_id: "app-id",
      configured: true,
      connected: true,
      last_sync_at: "2026-08-18T12:00:00Z",
      budget_account_external_ids: [],
    });
    vi.mocked(apiClient.post).mockResolvedValue({
      accounts_synced: 1,
      debtors_gbp: 0,
      message: "synced",
    });

    render(<QuickFileSettingsPanel />);
    expect(await screen.findByText("Connected")).toBeInTheDocument();
    expect(screen.getByText(/daily 1000-request quota/i)).toBeInTheDocument();
    expect(screen.getByText(/not Lunch Flow personal bank history/i)).toBeInTheDocument();

    const syncNow = screen.getByRole("button", { name: /Sync now/i });
    const importFull = screen.getByRole("button", { name: /Import full history/i });
    expect(syncNow).toBeEnabled();
    expect(importFull).toBeEnabled();

    await user.click(syncNow);
    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/finance/integrations/quickfile/sync");
    });
    expect(apiClient.post).not.toHaveBeenCalledWith(
      expect.stringContaining("force_full"),
    );

    vi.mocked(apiClient.post).mockClear();
    await user.click(importFull);
    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        "/finance/integrations/quickfile/sync?force_full=true",
      );
    });
    expect(apiClient.post).not.toHaveBeenCalledWith("/finance/integrations/quickfile/sync");
  });
});
