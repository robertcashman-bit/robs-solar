import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FinancePeriodScopeControl } from "@/components/finance/FinancePeriodScopeControl";

describe("FinancePeriodScopeControl", () => {
  it("renders period chips and notifies on change", async () => {
    const user = userEvent.setup();
    const onPeriodChange = vi.fn();
    render(
      <FinancePeriodScopeControl
        period="1m"
        onPeriodChange={onPeriodChange}
        showScope={false}
      />,
    );
    expect(screen.getByRole("button", { name: "Last month" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await user.click(screen.getByRole("button", { name: "3 months" }));
    expect(onPeriodChange).toHaveBeenCalledWith("3m");
  });

  it("renders dual personal and business period rows", async () => {
    const user = userEvent.setup();
    const onPersonal = vi.fn();
    const onBusiness = vi.fn();
    render(
      <FinancePeriodScopeControl
        dualPeriod
        period="1m"
        personalPeriod="1m"
        businessPeriod="3m"
        onPeriodChange={vi.fn()}
        onPersonalPeriodChange={onPersonal}
        onBusinessPeriodChange={onBusiness}
        showScope={false}
      />,
    );
    expect(screen.getByText("Personal")).toBeInTheDocument();
    expect(screen.getByText("Business")).toBeInTheDocument();
    const lastYearButtons = screen.getAllByRole("button", { name: "Last year" });
    await user.click(lastYearButtons[0]);
    expect(onPersonal).toHaveBeenCalledWith("12m");
    await user.click(lastYearButtons[1]);
    expect(onBusiness).toHaveBeenCalledWith("12m");
  });

  it("renders scope chips when enabled", async () => {
    const user = userEvent.setup();
    const onScopeChange = vi.fn();
    render(
      <FinancePeriodScopeControl
        period="1m"
        onPeriodChange={vi.fn()}
        scope="personal"
        onScopeChange={onScopeChange}
      />,
    );
    await user.click(screen.getByRole("button", { name: "business" }));
    expect(onScopeChange).toHaveBeenCalledWith("business");
  });
});
