"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const energyItems = [
  { href: "/energy", label: "Dashboard" },
  { href: "/energy/analytics", label: "Analytics" },
  { href: "/energy/octopus", label: "Octopus" },
  { href: "/energy/forecast", label: "Forecast" },
  { href: "/energy/scheduler", label: "Scheduler" },
  { href: "/energy/controls", label: "Inverter settings" },
  { href: "/energy/assistant", label: "Assistant" },
  { href: "/energy/diagnostics", label: "Diagnostics" },
];

export function EnergySubNav() {
  const pathname = usePathname();
  if (!pathname.startsWith("/energy")) {
    return null;
  }

  return (
    <nav
      aria-label="Energy section"
      className="mb-6 -mx-1 overflow-x-auto px-1 pb-1"
    >
      <div className="flex min-w-max gap-1 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-1">
        {energyItems.map((item) => {
          const active =
            pathname === item.href ||
            (item.href !== "/energy" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`shrink-0 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                active
                  ? "bg-amber-500/15 text-amber-700 dark:text-amber-300"
                  : "text-[var(--muted)] hover:bg-[var(--surface-elevated)] hover:text-[var(--foreground)]"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
