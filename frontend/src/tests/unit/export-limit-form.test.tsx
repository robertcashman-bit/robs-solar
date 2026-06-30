import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ExportLimitForm } from "@/components/controls/ExportLimitForm";

describe("ExportLimitForm", () => {
  it("disables controls in read-only mode", () => {
    render(<ExportLimitForm readOnlyMode onSubmit={vi.fn()} />);
    expect(screen.getByRole("status")).toHaveTextContent("read-only mode");
    expect(screen.getByRole("button", { name: "Review change" })).toBeDisabled();
  });

  it("shows validation error for invalid step", async () => {
    const user = userEvent.setup();
    render(<ExportLimitForm readOnlyMode={false} onSubmit={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Export limit (W)"), { target: { value: "2050" } });
    await user.click(screen.getByRole("button", { name: "Review change" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("multiple of 100");
  });

  it("requires confirmation before submit", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<ExportLimitForm readOnlyMode={false} onSubmit={onSubmit} />);
    await user.click(screen.getByRole("button", { name: "Review change" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
