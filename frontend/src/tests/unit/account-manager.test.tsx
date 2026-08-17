import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AccountManager } from "@/components/finance/AccountManager";

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

const types = [
  { value: "current", label: "Current" },
  { value: "credit_card", label: "Credit card" },
  { value: "capital_on_tap", label: "Capital on Tap" },
];

describe("AccountManager", () => {
  it("shows a credit limit field for Capital on Tap", async () => {
    const user = userEvent.setup();
    render(
      <AccountManager
        scope="business"
        accounts={[]}
        types={types}
        canEdit
        onChanged={async () => undefined}
        onError={() => undefined}
        onNotice={() => undefined}
      />,
    );

    expect(screen.queryByText("Credit limit (£)")).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Type"), "capital_on_tap");
    expect(screen.getByText("Credit limit (£)")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Needed for available credit")).toBeInTheDocument();
  });
});
