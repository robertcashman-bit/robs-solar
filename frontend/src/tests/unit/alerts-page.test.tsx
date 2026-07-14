import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";

import AlertsPage from "@/app/alerts/page";

const { mockGet, mockPost } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { username: "admin", role: "admin" },
    loading: false,
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/alerts",
}));

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: mockGet,
    post: mockPost,
  },
}));

describe("AlertsPage", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
  });

  it("shows empty state when no alerts", async () => {
    mockGet.mockResolvedValue({ alerts: [] });
    render(<AlertsPage />);
    expect(await screen.findByText("No active alerts")).toBeInTheDocument();
  });

  it("shows alerts with severity labels", async () => {
    mockGet.mockResolvedValue({
      alerts: [
        {
          id: 1,
          timestamp: "2026-06-28T12:00:00Z",
          severity: "warning",
          category: "battery",
          message: "Battery SOC below threshold",
          acknowledged: false,
        },
      ],
    });
    render(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByText("Battery SOC below threshold")).toBeInTheDocument();
    });
    expect(document.querySelector('[data-status="warning"]')).toBeTruthy();
    expect(screen.getByText("battery")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Acknowledge" })).toBeInTheDocument();
  });

  it("retries on refresh", async () => {
    mockGet.mockResolvedValue({ alerts: [] });
    const user = userEvent.setup();
    render(<AlertsPage />);
    await screen.findByText("No active alerts");
    const callsBefore = mockGet.mock.calls.length;
    await user.click(screen.getByRole("button", { name: "Refresh" }));
    expect(mockGet.mock.calls.length).toBeGreaterThan(callsBefore);
  });
});
