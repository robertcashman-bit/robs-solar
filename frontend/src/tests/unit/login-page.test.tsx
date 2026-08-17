import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "@/app/login/page";

const login = vi.fn();
const requestMagicCode = vi.fn(async () => ({
  message: "A new 6-digit sign-in code is on its way. It replaces any previous code.",
  expiresInSeconds: 600,
}));
const consumeMagicLink = vi.fn();

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: null,
    loading: false,
    magicCodeEnabled: true,
    magicCodeDevDelivery: false,
    login,
    requestMagicCode,
    verifyMagicCode: vi.fn(),
    consumeMagicLink,
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
}));

describe("LoginPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.history.replaceState({}, "", "/login");
    login.mockReset();
    requestMagicCode.mockClear();
    consumeMagicLink.mockReset();
  });

  it("prefills the owner email and offers a Desktop shortcut", () => {
    render(<LoginPage />);
    expect(screen.getByLabelText("Email or username")).toHaveValue(
      "robertdavidcashman@gmail.com",
    );
    expect(screen.getByRole("heading", { name: "Put Rob's Finance on your Desktop" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download the Desktop shortcut" })).toHaveAttribute(
      "href",
      "/RobsFinance.url",
    );
  });

  it("restores the last signed-in email", () => {
    window.localStorage.setItem("robs-finance-last-login-email", "viewer@example.com");
    render(<LoginPage />);
    expect(screen.getByLabelText("Email or username")).toHaveValue("viewer@example.com");
  });

  it("emails a fresh sign-in code and keeps password sign-in", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    const emailField = screen.getByLabelText("Email or username");
    await user.clear(emailField);
    await user.type(emailField, "rob@example.com");
    await user.click(screen.getByRole("button", { name: "Email me a sign-in code" }));

    expect(requestMagicCode).toHaveBeenCalledWith("rob@example.com");
    expect(await screen.findByText(/on its way/i)).toBeInTheDocument();
    expect(screen.getByLabelText("6-digit sign-in code")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Email me a new code" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in with password" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in with code" })).toBeInTheDocument();
  });

  it("emails a code automatically when the Desktop shortcut opens login", async () => {
    window.history.replaceState({}, "", "/login?send=1");
    render(<LoginPage />);

    await waitFor(() => {
      expect(requestMagicCode).toHaveBeenCalledWith("robertdavidcashman@gmail.com");
    });
    expect(await screen.findByLabelText("6-digit sign-in code")).toBeInTheDocument();
  });
});
