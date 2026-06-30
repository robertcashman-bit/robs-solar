import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ScheduleForm } from "@/components/controls/ScheduleForm";

describe("ScheduleForm", () => {
  it("disables controls in read-only mode", () => {
    render(<ScheduleForm readOnlyMode onSubmit={vi.fn()} />);
    expect(screen.getByRole("status")).toHaveTextContent("read-only mode");
    expect(screen.getByRole("button", { name: "Review change" })).toBeDisabled();
  });

  it("shows validation error for invalid time", async () => {
    const user = userEvent.setup();
    render(<ScheduleForm readOnlyMode={false} onSubmit={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Start time"), { target: { value: "25:00" } });
    await user.click(screen.getByRole("button", { name: "Review change" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
