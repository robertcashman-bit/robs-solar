import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { InstallerAccessPanel } from "@/components/settings/InstallerAccessPanel";

describe("InstallerAccessPanel", () => {
  it("explains view-only access and shows copy action", () => {
    render(<InstallerAccessPanel plantName="Greenacre" />);
    expect(screen.getByLabelText("Installer access request")).toBeInTheDocument();
    expect(screen.getByText(/Simple Solar/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /copy installer message/i })).toBeInTheDocument();
    expect(screen.getAllByText(/Greenacre/i).length).toBeGreaterThan(0);
  });
});
