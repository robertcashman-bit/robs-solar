import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FinanceAiAnalystCard } from "@/components/finance/FinanceAiAnalystCard";

const post = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    post: (...args: unknown[]) => post(...args),
  },
}));

describe("FinanceAiAnalystCard", () => {
  it("calls the interpret endpoint with the chosen prompt", async () => {
    post.mockResolvedValue({
      enabled: true,
      analysis: "FACT: ok",
      disclaimer: "not advice",
    });
    render(
      <FinanceAiAnalystCard user={{ username: "admin", role: "admin" }} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Analyse This Month" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/finance/finance-ai/interpret", {
        prompt: "Analyse This Month",
      }),
    );
    expect(await screen.findByText(/FACT: ok/)).toBeInTheDocument();
  });
});
