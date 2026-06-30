import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RestoreConfigButton } from "@/components/shared/RestoreConfigButton";

describe("RestoreConfigButton", () => {
  it("is disabled in read-only mode", () => {
    render(<RestoreConfigButton readOnlyMode onRestore={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Restore last known good" })).toBeDisabled();
  });

  it("shows confirmation dialog", async () => {
    const user = userEvent.setup();
    render(<RestoreConfigButton readOnlyMode={false} onRestore={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Restore last known good" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
