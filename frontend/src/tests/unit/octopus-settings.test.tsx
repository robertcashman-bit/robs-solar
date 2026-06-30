import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OctopusSettingsForm } from "@/components/settings/OctopusSettingsForm";
import { apiClient } from "@/lib/api-client";

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    post: vi.fn(),
    put: vi.fn(),
  },
}));

const baseStatus = {
  api_key_set: false,
  account_number: "",
  mpan: "",
  meter_serial: "",
  region: "C",
  configured: false,
};

describe("OctopusSettingsForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders fields and not-configured badge", () => {
    render(<OctopusSettingsForm initial={baseStatus} />);
    expect(screen.getByText("Octopus Energy")).toBeInTheDocument();
    expect(screen.getByText("Not configured")).toBeInTheDocument();
    expect(screen.getByLabelText(/API key/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Account number/i)).toBeInTheDocument();
  });

  it("auto-discovers and populates meter details", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.post).mockResolvedValue({
      account_number: "A-DBCBC021",
      mpan: "1900033149437",
      meter_serial: "24L3288488",
      region: "J",
    });

    render(<OctopusSettingsForm initial={baseStatus} />);
    await user.type(screen.getByLabelText(/API key/i), "sk_live_test");
    await user.type(screen.getByLabelText(/Account number/i), "A-DBCBC021");
    await user.click(screen.getByRole("button", { name: /auto-discover/i }));

    await waitFor(() => {
      expect((screen.getByLabelText(/^MPAN/i) as HTMLInputElement).value).toBe("1900033149437");
    });
    expect((screen.getByLabelText(/Meter serial/i) as HTMLInputElement).value).toBe("24L3288488");
    expect((screen.getByLabelText(/Region/i) as HTMLInputElement).value).toBe("J");
  });

  it("saves settings via the API", async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();
    vi.mocked(apiClient.put).mockResolvedValue({
      ...baseStatus,
      api_key_set: true,
      configured: true,
      account_number: "A-DBCBC021",
    });

    render(<OctopusSettingsForm initial={baseStatus} onSaved={onSaved} />);
    await user.type(screen.getByLabelText(/API key/i), "sk_live_test");
    await user.type(screen.getByLabelText(/Account number/i), "A-DBCBC021");
    await user.click(screen.getByRole("button", { name: /Save Octopus settings/i }));

    await waitFor(() => expect(apiClient.put).toHaveBeenCalledWith(
      "/octopus/settings",
      expect.objectContaining({ api_key: "sk_live_test", account_number: "A-DBCBC021" }),
    ));
    expect(onSaved).toHaveBeenCalled();
  });
});
