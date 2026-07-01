"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import {
  AlertIcon,
  BoltIcon,
  ChartIcon,
  GaugeIcon,
  SettingsIcon,
  ShieldIcon,
  SunIcon,
} from "@/components/shared/icons";
import { useAuth } from "@/lib/auth-context";
import { canViewAudit, canWrite } from "@/lib/permissions";
import { InstallAppBanner } from "@/components/shared/InstallAppBanner";

const navItems = [
  { href: "/", label: "Dashboard", icon: GaugeIcon },
  { href: "/analytics", label: "Analytics", icon: ChartIcon },
  { href: "/octopus", label: "Octopus", icon: ChartIcon },
  { href: "/forecast", label: "Forecast", icon: SunIcon },
  { href: "/scheduler", label: "Scheduler", icon: GaugeIcon },
  { href: "/controls", label: "Controls", icon: GaugeIcon, adminOnly: true },
  { href: "/assistant", label: "Assistant", icon: BoltIcon, adminOnly: true },
  { href: "/alerts", label: "Alerts", icon: AlertIcon },
  { href: "/audit", label: "Audit", icon: ShieldIcon, adminOnly: true },
  { href: "/settings", label: "Settings", icon: SettingsIcon },
];

function readStoredTheme(): "dark" | "light" {
  if (typeof window === "undefined") {
    return "dark";
  }
  const stored = window.localStorage.getItem("theme");
  return stored === "light" ? "light" : "dark";
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
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-400 to-orange-500 text-white shadow-lg">
            <SunIcon size={22} className="animate-pulse" />
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
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 text-white shadow-md transition-transform group-hover:scale-105">
              <SunIcon size={20} />
            </div>
            <div>
              <p className="text-[0.65rem] font-bold uppercase tracking-[0.14em] text-[var(--solar-dark)]">
                Rob&apos;s Solar
              </p>
              <h1 className="text-sm font-semibold leading-tight tracking-tight">Savings Control</h1>
            </div>
          </Link>

          {user ? (
            <div className="flex flex-wrap items-center gap-2 sm:gap-3">
              <nav
                aria-label="Main navigation"
                className="flex flex-wrap gap-0.5 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-1 shadow-sm"
              >
                {navItems.map((item) => {
                  if (item.adminOnly && !canWrite(user) && !canViewAudit(user)) {
                    return null;
                  }
                  const active = pathname === item.href;
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-medium transition-all sm:px-3 ${
                        active
                          ? "bg-gradient-to-r from-amber-500 to-orange-500 text-white shadow-sm"
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
        {children}
      </main>

      <footer className="border-t border-[var(--border)] py-5 text-center">
        <p className="text-xs text-[var(--muted)]">
          Rob&apos;s Solar — secure Sunsynk monitoring &amp; control
        </p>
      </footer>
    </div>
  );
}
