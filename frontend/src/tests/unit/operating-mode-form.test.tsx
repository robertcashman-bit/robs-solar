import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { OperatingModeForm } from "@/components/controls/OperatingModeForm";

describe("OperatingModeForm", () => {
  it("disables controls in read-only mode", () => {
    render(<OperatingModeForm readOnlyMode onSubmit={vi.fn()} />);
    expect(screen.getByRole("status")).toHaveTextContent("read-only mode");
    expect(screen.getByRole("button", { name: "Review change" })).toBeDisabled();
  });

  it("requires confirmation before submit", async () => {
    const user = userEvent.setup();
    render(<OperatingModeForm readOnlyMode={false} onSubmit={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Review change" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
