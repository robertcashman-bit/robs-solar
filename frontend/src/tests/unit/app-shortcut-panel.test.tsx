import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppShortcutPanel } from "@/components/settings/AppShortcutPanel";

describe("AppShortcutPanel", () => {
  it("shows Dock, Desktop, and phone shortcut instructions without Energy", () => {
    render(<AppShortcutPanel />);
    expect(screen.getByRole("heading", { name: "App shortcut" })).toBeInTheDocument();
    expect(screen.getAllByText(/RobsFinance.app/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Install Rob's Finance/)).toBeInTheDocument();
    expect(screen.getByText(/install-mac-shortcut.sh/)).toBeInTheDocument();
    expect(screen.getByText(/Rob Finance App/)).toBeInTheDocument();
    expect(screen.getByText(/Add to Home Screen/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download the Desktop shortcut" })).toHaveAttribute(
      "href",
      "/RobsFinance.url",
    );
    expect(screen.queryByText(/Sunsynk/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Energy/i)).not.toBeInTheDocument();
  });
});
