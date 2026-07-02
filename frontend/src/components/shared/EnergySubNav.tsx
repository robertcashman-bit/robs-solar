"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const energyItems = [
  { href: "/energy", label: "Dashboard" },
  { href: "/energy/analytics", label: "Analytics" },
  { href: "/energy/octopus", label: "Octopus" },
  { href: "/energy/forecast", label: "Forecast" },
  { href: "/energy/scheduler", label: "Scheduler" },
  { href: "/energy/controls", label: "Controls", adminOnly: true },
  { href: "/energy/assistant", label: "Assistant", adminOnly: true },
];

type EnergySubNavProps = {
  isAdmin?: boolean;
};

export function EnergySubNav({ isAdmin = false }: EnergySubNavProps) {
  const pathname = usePathname();
  if (!pathname.startsWith("/energy")) {
    return null;
  }

  return (
    <nav
      aria-label="Energy section"
      className="mb-6 flex flex-wrap gap-1 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-1"
    >
      {energyItems.map((item) => {
        if (item.adminOnly && !isAdmin) {
          return null;
        }
        const active =
          pathname === item.href ||
          (item.href !== "/energy" && pathname.startsWith(item.href));
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
              active
                ? "bg-amber-500/15 text-amber-700 dark:text-amber-300"
                : "text-[var(--muted)] hover:text-[var(--foreground)]"
            }`}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
