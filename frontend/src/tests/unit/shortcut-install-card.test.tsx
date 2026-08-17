import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ShortcutInstallCard } from "@/components/shared/ShortcutInstallCard";

describe("ShortcutInstallCard", () => {
  it("offers Windows, Mac, and phone shortcut installers", () => {
    render(<ShortcutInstallCard />);
    expect(screen.getByRole("heading", { name: "Put Rob's Finance on your Desktop" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download the Desktop shortcut" })).toHaveAttribute(
      "href",
      "/RobsFinance.url",
    );
    expect(screen.getByText(/install-windows-shortcut.ps1/)).toBeInTheDocument();
    expect(screen.getByText(/install-mac-shortcut.sh/)).toBeInTheDocument();
    expect(screen.getByText(/Add to Home Screen/)).toBeInTheDocument();
  });
});
