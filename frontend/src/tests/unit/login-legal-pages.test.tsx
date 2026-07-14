import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import LoginPage from "@/app/login/page";
import PrivacyPage from "@/app/privacy/page";
import TermsPage from "@/app/terms/page";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: null,
    loading: false,
    login: vi.fn(),
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
}));

describe("LoginPage", () => {
  it("renders sign-in form with legal links", () => {
    render(<LoginPage />);
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByText(/Personal finance, business tracking, and home energy monitoring/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "terms" })).toHaveAttribute("href", "/terms");
    expect(screen.getByRole("link", { name: "privacy policy" })).toHaveAttribute("href", "/privacy");
  });

  it("has required username and password fields", () => {
    render(<LoginPage />);
    expect(screen.getByLabelText("Username")).toBeRequired();
    expect(screen.getByLabelText("Password")).toBeRequired();
  });
});

describe("Legal pages", () => {
  it("renders privacy page with navigation", () => {
    render(<PrivacyPage />);
    expect(screen.getByRole("heading", { name: "Privacy policy" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Back to sign in/i })).toHaveAttribute("href", "/login");
    expect(screen.getByRole("link", { name: "Terms of use" })).toHaveAttribute("href", "/terms");
  });

  it("renders terms page with energy mention", () => {
    render(<TermsPage />);
    expect(screen.getByRole("heading", { name: "Terms of use" })).toBeInTheDocument();
    expect(screen.getByText(/home solar and battery monitoring/)).toBeInTheDocument();
  });
});
