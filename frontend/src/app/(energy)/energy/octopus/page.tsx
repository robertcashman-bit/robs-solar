"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/shared/AppShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { DispatchWindows } from "@/components/scheduler/DispatchWindows";
import { ChartIcon } from "@/components/shared/icons";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { dispatchResponseSchema, octopusTariffSchema, type OctopusTariff } from "@/lib/schemas";

type PriceRate = { valid_from: string; value_inc_vat: number };

type AgilePayload = {
  current?: PriceRate;
  rates: PriceRate[];
  cheapest_slots?: PriceRate[];
  expensive_slots?: PriceRate[];
  plunge_pricing: boolean;
};

function priceColor(p: number) {
  if (p < 0) return "bg-violet-500";
  if (p < 10) return "bg-emerald-500";
  if (p < 25) return "bg-amber-500";
  return "bg-rose-500";
}

function tariffLabel(family: string) {
  if (family === "IOG") return "Intelligent Octopus Go";
  if (family === "AGILE") return "Octopus Agile";
  if (family === "OUTGOING") return "Outgoing";
  return "Your tariff";
}

export default function OctopusPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [tariff, setTariff] = useState<OctopusTariff | null>(null);
  const [agile, setAgile] = useState<AgilePayload | null>(null);
  const [dispatches, setDispatches] = useState(
    null as ReturnType<typeof dispatchResponseSchema.parse> | null,
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    void (async () => {
      try {
        const data = await apiClient.get<{
          tariff?: unknown;
          agile?: AgilePayload;
          rates?: PriceRate[];
          current?: PriceRate;
          cheapest_slots?: PriceRate[];
          expensive_slots?: PriceRate[];
          plunge_pricing?: boolean;
        }>("/octopus/prices");
        if (data.tariff) {
          setTariff(octopusTariffSchema.parse(data.tariff));
        }
        const agileData = data.agile ?? {
          current: data.current,
          rates: data.rates ?? [],
          cheapest_slots: data.cheapest_slots,
          expensive_slots: data.expensive_slots,
          plunge_pricing: data.plunge_pricing ?? false,
        };
        setAgile(agileData);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Octopus unavailable");
      }
    })();
    void (async () => {
      try {
        const data = await apiClient.get("/octopus/dispatches");
        setDispatches(dispatchResponseSchema.parse(data));
      } catch {
        setDispatches(null);
      }
    })();
  }, [user]);

  if (authLoading || !user) return null;

  const agileCurrent = agile?.current?.value_inc_vat;

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Tariff"
          icon={<ChartIcon size={22} />}
          title={<span className="text-gradient-solar">Octopus Energy</span>}
          description="Your account tariff rates for savings, plus Agile market reference for scheduling."
        />
        {error ? <ErrorBanner message={error} /> : null}

        {tariff?.import_rate_pence != null ? (
          <section className="solar-card">
            <p className="solar-eyebrow">Your bill rates (Greenacre)</p>
            <h3 className="mt-1 text-lg font-semibold">
              {tariffLabel(tariff.tariff_family)}
            </h3>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 text-center">
                <p className="text-xs uppercase tracking-wider text-[var(--muted)]">Import</p>
                <p className="mt-2 text-4xl font-bold tabular-nums text-amber-600 dark:text-amber-400">
                  {tariff.import_rate_pence.toFixed(2)}p
                </p>
                <p className="text-sm text-[var(--muted)]">per kWh</p>
              </div>
              {tariff.export_rate_pence != null ? (
                <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 text-center">
                  <p className="text-xs uppercase tracking-wider text-[var(--muted)]">Export (SEG)</p>
                  <p className="mt-2 text-4xl font-bold tabular-nums text-sky-600 dark:text-sky-400">
                    {tariff.export_rate_pence.toFixed(2)}p
                  </p>
                  <p className="text-sm text-[var(--muted)]">per kWh</p>
                </div>
              ) : null}
            </div>
            <p className="mt-3 text-xs text-[var(--muted)]">
              Region {tariff.region} · Import {tariff.import_tariff_code}
              {tariff.export_tariff_code ? ` · Export ${tariff.export_tariff_code}` : ""}
            </p>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Dashboard savings calculations use these rates, not the Agile chart below.
            </p>
          </section>
        ) : null}

        <section className="solar-card">
          <DispatchWindows dispatches={dispatches} />
        </section>

        {agile?.plunge_pricing ? (
          <p className="rounded-xl border border-violet-400/40 bg-violet-500/10 px-4 py-3 text-sm">
            Agile plunge pricing active in your region — wholesale market reference only.
          </p>
        ) : null}

        {agileCurrent != null ? (
          <div className="solar-card text-center">
            <p className="solar-eyebrow">Agile market now (region {tariff?.region ?? "—"})</p>
            <p className="mt-2 text-5xl font-bold tabular-nums">{agileCurrent.toFixed(2)}p/kWh</p>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Half-hourly wholesale reference for scheduler overlay — not your IOG bill rate.
            </p>
          </div>
        ) : null}

        {agile?.rates?.length ? (
          <section className="solar-card">
            <h3 className="solar-section-title">Agile market — next 24 hours</h3>
            <div className="mt-4 flex h-40 items-end gap-0.5">
              {agile.rates.slice(0, 48).map((r, i) => (
                <div
                  key={`${r.valid_from}-${i}`}
                  className={`min-w-[4px] flex-1 rounded-t ${priceColor(r.value_inc_vat)}`}
                  style={{ height: `${Math.min(100, Math.max(8, r.value_inc_vat * 3))}%` }}
                  title={`${r.value_inc_vat.toFixed(2)}p`}
                />
              ))}
            </div>
          </section>
        ) : null}

        {agile?.cheapest_slots?.length ? (
          <section className="solar-card grid gap-4 sm:grid-cols-2">
            <div>
              <h3 className="solar-section-title text-emerald-600 dark:text-emerald-400">
                Cheapest Agile slots
              </h3>
              <ul className="mt-2 space-y-1 text-sm">
                {agile.cheapest_slots.map((r) => (
                  <li key={r.valid_from} className="tabular-nums">
                    {new Date(r.valid_from).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}{" "}
                    — {r.value_inc_vat.toFixed(2)}p/kWh
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="solar-section-title text-rose-600 dark:text-rose-400">
                Most expensive Agile slots
              </h3>
              <ul className="mt-2 space-y-1 text-sm">
                {agile.expensive_slots?.map((r) => (
                  <li key={r.valid_from} className="tabular-nums">
                    {new Date(r.valid_from).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}{" "}
                    — {r.value_inc_vat.toFixed(2)}p/kWh
                  </li>
                ))}
              </ul>
            </div>
          </section>
        ) : null}
      </div>
    </AppShell>
  );
}
