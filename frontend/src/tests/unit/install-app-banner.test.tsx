import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { InstallAppBanner } from "@/components/shared/InstallAppBanner";

const DISMISS_KEY = "robs-finance-install-dismissed";

describe("InstallAppBanner", () => {
  afterEach(() => {
    localStorage.clear();
  });

  it("shows a desktop shortcut restore link until dismissed", () => {
    render(<InstallAppBanner />);
    expect(screen.getByText(/Install Rob/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "App shortcut" })).toHaveAttribute(
      "href",
      "/settings#app-shortcut",
    );
  });

  it("does not become eligible after beforeinstallprompt when already dismissed", () => {
    localStorage.setItem(DISMISS_KEY, "1");
    render(<InstallAppBanner />);
    fireEvent(window, new Event("beforeinstallprompt", { cancelable: true }));
    expect(screen.queryByText(/Install Rob/)).not.toBeInTheDocument();
  });
});
