export type ScheduleWindow = {
  start: string;
  end: string;
  action: "charge" | "discharge" | "idle";
  power_w?: number;
};

export type StrategyPreset = {
  id: string;
  label: string;
  tagline: string;
  description: string;
  bestFor: string;
  windows: ScheduleWindow[];
};

export const STRATEGY_PRESETS: StrategyPreset[] = [
  {
    id: "overnight-charge",
    label: "Overnight charge",
    tagline: "Maximum self-consumption",
    description:
      "Charge the battery from the grid during cheap overnight Agile slots, then use stored energy through the day.",
    bestFor: "Winter evenings and plunge-pricing nights",
    windows: [{ start: "23:30", end: "05:30", action: "charge", power_w: 3000 }],
  },
  {
    id: "peak-export",
    label: "Peak export",
    tagline: "Export-friendly",
    description:
      "Discharge during late-afternoon peak export windows when rates are often highest and home load is lower.",
    bestFor: "Summer weekdays with strong afternoon export prices",
    windows: [{ start: "16:00", end: "19:00", action: "discharge", power_w: 5000 }],
  },
  {
    id: "winter-conservative",
    label: "Winter conservative",
    tagline: "Winter reserve",
    description:
      "Top up the battery overnight and hold through the evening peak. Avoids draining the battery when solar is weak.",
    bestFor: "November–February when PV is low",
    windows: [
      { start: "00:00", end: "06:00", action: "charge", power_w: 2000 },
      { start: "17:00", end: "21:00", action: "idle" },
    ],
  },
  {
    id: "summer-export",
    label: "Summer maximise export",
    tagline: "Export-friendly",
    description:
      "Push surplus solar to the grid during midday when generation is highest and self-consumption is often already covered.",
    bestFor: "Long sunny days May–August",
    windows: [{ start: "10:00", end: "16:00", action: "discharge", power_w: 6000 }],
  },
  {
    id: "peak-protection",
    label: "Peak price protection",
    tagline: "Peak-price protection",
    description:
      "Keep the battery for the expensive 4–7pm window. Charge cheaply before, discharge or idle during peak import rates.",
    bestFor: "Agile tariffs with expensive evening peaks",
    windows: [
      { start: "02:00", end: "05:00", action: "charge", power_w: 2500 },
      { start: "16:00", end: "19:00", action: "discharge", power_w: 4000 },
    ],
  },
  {
    id: "manual-idle",
    label: "Reset to default",
    tagline: "Manual mode",
    description:
      "Clear scheduled slots and let the inverter follow its current work mode without time-based overrides.",
    bestFor: "When you want full manual control",
    windows: [{ start: "00:00", end: "23:59", action: "idle" }],
  },
];

export type PriceRate = { valid_from: string; value_inc_vat: number };

export function priceColorClass(pence: number): string {
  if (pence < 0) return "bg-violet-500/80";
  if (pence < 10) return "bg-emerald-500/80";
  if (pence < 25) return "bg-amber-500/80";
  return "bg-rose-500/80";
}

export function minutesFromMidnight(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

export function slotPercent(hhmm: string): number {
  return (minutesFromMidnight(hhmm) / (24 * 60)) * 100;
}
