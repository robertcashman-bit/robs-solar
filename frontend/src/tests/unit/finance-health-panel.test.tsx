import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FinanceHealthPanel } from "@/components/finance/FinanceHealthPanel";
import { ApiError } from "@/lib/api-client";

const getMock = vi.fn();

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return {
    ...actual,
    apiClient: {
      get: (...args: unknown[]) => getMock(...args),
      post: vi.fn(),
    },
  };
});

describe("FinanceHealthPanel", () => {
  it("shows persistence warning and self-heal action", async () => {
    getMock.mockImplementation(async (path: string) => {
      if (path === "/finance/health" || path.startsWith("/finance/health?")) {
        return {
          ok: true,
          db_read: null,
          db_write: null,
          light: true,
          data_source: "finance",
          database_backend: "sqlite",
          ephemeral_database: true,
          web_backup_configured: false,
          finance_bank_reads_ready: true,
          last_import: null,
          last_backup: null,
          needs_review: true,
          integrations: {
            quickfile: {
              configured: true,
              connected: true,
              last_sync_at: "2026-08-17T10:00:00Z",
            },
            lunchflow: {
              configured: true,
              connected: true,
              last_sync_at: "2026-08-17T10:05:00Z",
            },
          },
        };
      }
      return {};
    });
    render(<FinanceHealthPanel canEdit />);
    expect(await screen.findByText("Finance health")).toBeInTheDocument();
    expect(await screen.findByText(/wiped on deploy/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Self-heal caches" })).toBeInTheDocument();
    expect(screen.getByText(/none yet — tap Backup now/i)).toBeInTheDocument();
    expect(screen.getByText(/Data source: finance/i)).toBeInTheDocument();
    expect(screen.getByText(/QuickFile: configured/i)).toBeInTheDocument();
    expect(screen.getByText(/Lunch Flow: connected/i)).toBeInTheDocument();
    expect(screen.getByText(/not probed \(light\)/i)).toBeInTheDocument();
    expect(screen.queryByText(/TrueLayer/i)).not.toBeInTheDocument();
    expect(screen.getByText(/do not mean bank balances are simulated/i)).toBeInTheDocument();
    expect(screen.queryByText(/Loading health/i)).not.toBeInTheDocument();
  });

  it("leaves Loading and shows Retry after a soft-fail timeout", async () => {
    getMock.mockRejectedValue(new ApiError("The server took too long to respond.", 504));
    render(<FinanceHealthPanel canEdit />);
    expect(await screen.findByText(/took too long/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText(/Loading health/i)).not.toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(screen.getByText(/Health unavailable/i)).toBeInTheDocument();
  });
});
