"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { EnergySubNav } from "@/components/shared/EnergySubNav";
import {
  AlertIcon,
  ChartIcon,
  GaugeIcon,
  SettingsIcon,
  SunIcon,
  WalletIcon,
} from "@/components/shared/icons";
import { useAuth } from "@/lib/auth-context";
import { canWrite } from "@/lib/permissions";
import { InstallAppBanner } from "@/components/shared/InstallAppBanner";

const navItems = [
  { href: "/", label: "Overview", icon: GaugeIcon },
  { href: "/finance/personal", label: "Personal", icon: WalletIcon },
  { href: "/finance/business", label: "Business", icon: WalletIcon },
  { href: "/finance/debts", label: "Debts", icon: WalletIcon },
  { href: "/finance/cash-flow", label: "Cash Flow", icon: ChartIcon },
  { href: "/finance/budget", label: "Budget", icon: ChartIcon },
  { href: "/finance/reports", label: "Reports", icon: ChartIcon },
  { href: "/energy", label: "Energy", icon: SunIcon },
  { href: "/settings", label: "Settings", icon: SettingsIcon },
];

function readStoredTheme(): "dark" | "light" {
  if (typeof window === "undefined") {
    return "dark";
  }
  const stored = window.localStorage.getItem("theme");
  return stored === "light" ? "light" : "dark";
}

function isNavActive(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }
  if (href === "/energy") {
    return pathname === "/energy" || pathname.startsWith("/energy/");
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user, logout, loading } = useAuth();
  const [theme, setTheme] = useState<"dark" | "light">(readStoredTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    window.localStorage.setItem("theme", next);
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-400 to-teal-600 text-white shadow-lg">
            <WalletIcon size={22} className="animate-pulse" />
          </div>
          <p className="text-sm text-[var(--muted)]">Loading session…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col text-[var(--foreground)]">
      <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[var(--surface-elevated)]/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <Link href="/" className="group flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-400 to-teal-600 text-white shadow-md transition-transform group-hover:scale-105">
              <WalletIcon size={20} />
            </div>
            <div>
              <p className="text-[0.65rem] font-bold uppercase tracking-[0.14em] text-emerald-700 dark:text-emerald-400">
                Rob&apos;s Finance
              </p>
              <h1 className="text-sm font-semibold leading-tight tracking-tight">Finance Dashboard</h1>
            </div>
          </Link>

          {user ? (
            <div className="flex flex-wrap items-center gap-2 sm:gap-3">
              <nav
                aria-label="Main navigation"
                className="flex max-w-[min(100vw-2rem,52rem)] flex-wrap gap-0.5 overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--surface)] p-1 shadow-sm"
              >
                {navItems.map((item) => {
                  const active = isNavActive(pathname, item.href);
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={`inline-flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-medium transition-all sm:px-3 ${
                        active
                          ? "bg-gradient-to-r from-emerald-500 to-teal-600 text-white shadow-sm"
                          : "text-[var(--muted)] hover:bg-[var(--surface-elevated)] hover:text-[var(--foreground)]"
                      }`}
                    >
                      <Icon size={15} className={active ? "opacity-95" : "opacity-70"} />
                      <span className="hidden sm:inline">{item.label}</span>
                      <span className="sr-only sm:hidden">{item.label}</span>
                    </Link>
                  );
                })}
              </nav>

              <Link
                href="/alerts"
                className="inline-flex items-center gap-1 rounded-lg border border-[var(--border)] px-2.5 py-1.5 text-sm text-[var(--muted)] hover:text-[var(--foreground)]"
                aria-label="Alerts"
              >
                <AlertIcon size={16} />
              </Link>

              <span className="hidden items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-medium shadow-sm md:inline-flex">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                {user.username}
                <span className="text-[var(--muted)]">· {user.role}</span>
              </span>

              <button type="button" onClick={toggleTheme} className="solar-btn-ghost text-xs sm:text-sm">
                {theme === "dark" ? "Light" : "Dark"}
              </button>
              <button type="button" onClick={() => void logout()} className="solar-btn-ghost text-xs sm:text-sm">
                Log out
              </button>
            </div>
          ) : null}
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:py-8">
        {user ? <InstallAppBanner /> : null}
        {user ? <EnergySubNav isAdmin={canWrite(user)} /> : null}
        {children}
      </main>

      <footer className="border-t border-[var(--border)] py-5 text-center">
        <p className="text-xs text-[var(--muted)]">
          Rob&apos;s Finance — personal &amp; business tracking · Energy / Solar in{" "}
          <Link href="/energy" className="underline">
            Energy section
          </Link>
        </p>
      </footer>
    </div>
  );
}
