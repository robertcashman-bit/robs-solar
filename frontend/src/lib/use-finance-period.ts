"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  DEFAULT_FINANCE_PERIOD,
  DEFAULT_FINANCE_SCOPE,
  type FinancePeriodKey,
  type FinancePeriodPrefs,
  type FinancePeriodScope,
  parseFinancePeriod,
  parseFinanceScope,
  readStoredPeriodPrefs,
  writeStoredPeriodPrefs,
} from "@/lib/finance-period";

type Options = {
  /** When true, sync personalPeriod and businessPeriod independently in the URL. */
  dualPeriod?: boolean;
  /** Hide or fix scope (e.g. personal page always personal). */
  fixedScope?: FinancePeriodScope;
  defaultScope?: FinancePeriodScope;
  /** Fallback when URL (and, unless preferDefaultPeriod, stored) have no period. */
  defaultPeriod?: FinancePeriodKey;
  /**
   * When set with defaultPeriod, URL wins then defaultPeriod — stored period is
   * ignored so Personal/Business can default to MTD on each visit without a query.
   */
  preferDefaultPeriod?: boolean;
};

function currentParams(): URLSearchParams {
  if (typeof window === "undefined") return new URLSearchParams();
  return new URLSearchParams(window.location.search);
}

function readPrefs(opts: Options): FinancePeriodPrefs {
  const params = currentParams();
  const stored = readStoredPeriodPrefs();
  const fallback = opts.defaultPeriod ?? DEFAULT_FINANCE_PERIOD;
  // preferDefaultPeriod: URL wins, then page default (e.g. mtd on Personal/Business).
  const period = parseFinancePeriod(
    params.get("period")
      ?? (opts.preferDefaultPeriod ? opts.defaultPeriod : stored.period),
    fallback,
  );
  const personalPeriod = parseFinancePeriod(
    params.get("personal_period") ?? stored.personalPeriod ?? period,
    period,
  );
  const businessPeriod = parseFinancePeriod(
    params.get("business_period") ?? stored.businessPeriod ?? period,
    period,
  );
  const scope =
    opts.fixedScope
    ?? parseFinanceScope(
      params.get("scope") ?? stored.scope,
      opts.defaultScope ?? DEFAULT_FINANCE_SCOPE,
    );
  return { period, personalPeriod, businessPeriod, scope };
}

function replaceUrl(prefs: FinancePeriodPrefs, opts: Options): void {
  if (typeof window === "undefined") return;
  const params = currentParams();
  if (opts.dualPeriod) {
    params.set("personal_period", prefs.personalPeriod);
    params.set("business_period", prefs.businessPeriod);
    params.delete("period");
  } else {
    params.set("period", prefs.period);
    params.delete("personal_period");
    params.delete("business_period");
  }
  if (opts.fixedScope) {
    params.delete("scope");
  } else {
    params.set("scope", prefs.scope);
  }
  const query = params.toString();
  const next = query ? `${window.location.pathname}?${query}` : window.location.pathname;
  window.history.replaceState(window.history.state, "", next);
}

export function useFinancePeriod(options: Options = {}) {
  const dualPeriod = Boolean(options.dualPeriod);
  const [prefs, setPrefs] = useState<FinancePeriodPrefs>(() => readPrefs(options));

  useEffect(() => {
    const onPop = () => setPrefs(readPrefs(options));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.dualPeriod, options.fixedScope, options.defaultScope, options.defaultPeriod, options.preferDefaultPeriod]);

  const persist = useCallback(
    (next: FinancePeriodPrefs) => {
      setPrefs(next);
      writeStoredPeriodPrefs(next);
      replaceUrl(next, options);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [options.dualPeriod, options.fixedScope, options.defaultScope, options.defaultPeriod, options.preferDefaultPeriod],
  );

  const setPeriod = useCallback(
    (period: FinancePeriodKey) => {
      persist({
        ...prefs,
        period,
        personalPeriod: dualPeriod ? prefs.personalPeriod : period,
        businessPeriod: dualPeriod ? prefs.businessPeriod : period,
      });
    },
    [dualPeriod, persist, prefs],
  );

  const setPersonalPeriod = useCallback(
    (personalPeriod: FinancePeriodKey) => {
      persist({ ...prefs, personalPeriod, period: personalPeriod });
    },
    [persist, prefs],
  );

  const setBusinessPeriod = useCallback(
    (businessPeriod: FinancePeriodKey) => {
      persist({ ...prefs, businessPeriod, period: businessPeriod });
    },
    [persist, prefs],
  );

  const setScope = useCallback(
    (scope: FinancePeriodScope) => {
      if (options.fixedScope) return;
      persist({ ...prefs, scope });
    },
    [options.fixedScope, persist, prefs],
  );

  return useMemo(
    () => ({
      period: prefs.period,
      personalPeriod: prefs.personalPeriod,
      businessPeriod: prefs.businessPeriod,
      scope: options.fixedScope ?? prefs.scope,
      dualPeriod,
      setPeriod,
      setPersonalPeriod,
      setBusinessPeriod,
      setScope,
    }),
    [
      prefs,
      options.fixedScope,
      dualPeriod,
      setPeriod,
      setPersonalPeriod,
      setBusinessPeriod,
      setScope,
    ],
  );
}
