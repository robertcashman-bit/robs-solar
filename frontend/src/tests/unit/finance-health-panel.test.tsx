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
          database_backend: "sqlite",
          ephemeral_database: true,
          web_backup_configured: false,
          last_import: null,
          last_backup: null,
          needs_review: true,
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
  });
});
