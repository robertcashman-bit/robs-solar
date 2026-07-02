"use client";

import Link from "next/link";

import { GaugeIcon, ChartIcon, SunIcon } from "@/components/shared/icons";

const actions = [
  {
    href: "/energy/scheduler",
    label: "Overnight charge",
    desc: "Schedule cheap-period charging",
    icon: GaugeIcon,
  },
  {
    href: "/energy/octopus",
    label: "Agile prices",
    desc: "Find cheapest half-hours",
    icon: ChartIcon,
  },
  {
    href: "/energy/forecast",
    label: "Solar forecast",
    desc: "Skip grid charge if sunny",
    icon: SunIcon,
  },
  {
    href: "/energy/controls",
    label: "Battery limits",
    desc: "Charge / discharge caps",
    icon: GaugeIcon,
  },
];

export function QuickActionsStrip() {
  return (
    <section aria-label="Quick savings actions" className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
      {actions.map((item) => {
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            className="group flex items-start gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3 transition-all hover:border-[var(--border-strong)] hover:bg-[var(--surface-elevated)] hover:shadow-md"
          >
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-amber-400/20 to-orange-500/10 text-[var(--solar-dark)] transition-transform group-hover:scale-105">
              <Icon size={18} />
            </span>
            <span>
              <span className="block text-sm font-semibold">{item.label}</span>
              <span className="block text-xs text-[var(--muted)]">{item.desc}</span>
            </span>
          </Link>
        );
      })}
    </section>
  );
}
