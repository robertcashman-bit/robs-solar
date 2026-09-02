import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "@/app/login/page";

const login = vi.fn();
const requestMagicCode = vi.fn(async () => ({
  message: "Check your email for a 6-digit code. Any older code no longer works.",
  expiresInSeconds: 600,
}));
const verifyMagicCode = vi.fn();
const consumeMagicLink = vi.fn();
const apiGet = vi.fn(async (path: string) => {
  void path;
  return { status: "ok" };
});

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: null,
    loading: false,
    authResolved: true,
    magicCodeEnabled: true,
    magicCodeDevDelivery: false,
    login,
    requestMagicCode,
    verifyMagicCode,
    consumeMagicLink,
  }),
}));

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return {
    ...actual,
    apiClient: {
      get: (path: string) => apiGet(path),
    },
  };
});

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
    verifyMagicCode.mockReset();
    consumeMagicLink.mockReset();
    apiGet.mockClear();
    apiGet.mockResolvedValue({ status: "ok" });
  });

  it("warms the API with a health ping on mount", async () => {
    render(<LoginPage />);
    await waitFor(() => {
      expect(apiGet).toHaveBeenCalledWith("/health");
    });
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

  it("signs in with password by default and keeps remember-me on", async () => {
    const user = userEvent.setup();
    login.mockResolvedValue(undefined);
    render(<LoginPage />);

    expect(screen.getByRole("button", { name: "Sign in" })).toHaveClass("solar-btn-primary");
    expect(screen.getByLabelText("Stay signed in for 30 days")).toBeChecked();
    expect(screen.queryByLabelText("6-digit sign-in code")).not.toBeInTheDocument();
    // Code send is behind a collapsed details — not the default CTA.
    expect(screen.getByText("Email me a code instead").closest("details")).not.toHaveAttribute(
      "open",
    );

    await user.clear(screen.getByLabelText("Email or username"));
    await user.type(screen.getByLabelText("Email or username"), "rob@example.com");
    await user.type(screen.getByLabelText("Password"), "secret-pass");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(login).toHaveBeenCalledWith("rob@example.com", "secret-pass", true);
  });

  it("keeps email code optional behind a collapsed link", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    expect(screen.getByText("Email me a code instead")).toBeInTheDocument();
    expect(requestMagicCode).not.toHaveBeenCalled();

    await user.click(screen.getByText("Email me a code instead"));
    await user.click(screen.getByRole("button", { name: "Email me a sign-in code" }));

    expect(requestMagicCode).toHaveBeenCalledWith("robertdavidcashman@gmail.com");
    expect(await screen.findByText(/Check your email/i)).toBeInTheDocument();
    expect(screen.getByLabelText("6-digit sign-in code")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in with code" })).toBeInTheDocument();
    // Password sign-in remains the primary path.
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("emails a code automatically when an old Desktop shortcut opens login?send=1", async () => {
    window.history.replaceState({}, "", "/login?send=1");
    render(<LoginPage />);

    await waitFor(() => {
      expect(requestMagicCode).toHaveBeenCalledWith("robertdavidcashman@gmail.com");
    });
    expect(await screen.findByLabelText("6-digit sign-in code")).toBeInTheDocument();
  });
});
