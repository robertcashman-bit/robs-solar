import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FinanceHealthPanel } from "@/components/finance/FinanceHealthPanel";

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: vi.fn(async (path: string) => {
      if (path === "/finance/health") {
        return {
          ok: true,
          db_read: true,
          db_write: true,
          data_source: "finance",
          database_backend: "sqlite",
          ephemeral_database: true,
          web_backup_configured: false,
          finance_bank_reads_ready: true,
          last_import: null,
          last_backup: null,
          needs_review: true,
          integrations: {
            quickfile: { configured: true, last_sync_at: "2026-08-17T10:00:00Z" },
            lunchflow: {
              configured: true,
              connected: true,
              last_sync_at: "2026-08-17T10:05:00Z",
            },
            truelayer: { configured: false, connected: false, last_sync_at: null },
          },
        };
      }
      return {};
    }),
    post: vi.fn(),
  },
}));

describe("FinanceHealthPanel", () => {
  it("shows persistence warning and self-heal action", async () => {
    render(<FinanceHealthPanel canEdit />);
    expect(await screen.findByText("Finance health")).toBeInTheDocument();
    expect(await screen.findByText(/wiped on deploy/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Self-heal caches" })).toBeInTheDocument();
    expect(screen.getByText(/none yet — tap Backup now/i)).toBeInTheDocument();
    expect(screen.getByText(/Data source: finance/i)).toBeInTheDocument();
    expect(screen.getByText(/QuickFile: configured/i)).toBeInTheDocument();
    expect(screen.getByText(/Lunch Flow: connected/i)).toBeInTheDocument();
    expect(screen.getByText(/TrueLayer: not configured/i)).toBeInTheDocument();
    expect(screen.getByText(/do not mean bank balances are simulated/i)).toBeInTheDocument();
  });
});
