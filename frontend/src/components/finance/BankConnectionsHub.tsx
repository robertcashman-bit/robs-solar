"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { z } from "zod";

import { BankConnectionCard } from "@/components/finance/BankConnectionCard";
import {
  CONNECTION_SEARCH,
  ENABLE_BANKING_CP_URL,
  mapOpenBankingConnectError,
} from "@/lib/bank-connections";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import {
  bankConnectionsResponseSchema,
  openBankingConfigStatusSchema,
  openBankingConnectResponseSchema,
  openBankingInstitutionSchema,
  openBankingSyncResultSchema,
  type BankConnectionItem,
  type OpenBankingConfigStatus,
} from "@/lib/finance-schemas";
import { canWrite } from "@/lib/permissions";

type BankConnectionsHubProps = {
  readOnly?: boolean;
};

export function BankConnectionsHub({ readOnly = false }: BankConnectionsHubProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAuth();
  const writable = canWrite(user) && !readOnly;

  const [connections, setConnections] = useState<BankConnectionItem[]>([]);
  const [obStatus, setObStatus] = useState<OpenBankingConfigStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const obConfigured = obStatus?.configured ?? false;
  const obNeedsActivation = obConfigured && obStatus?.provider_ready === false;

  const load = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const [cards, statusResponse] = await Promise.all([
        apiClient.get<unknown>("/finance/bank-connections"),
        apiClient.get<unknown>("/finance/integrations/open-banking/status"),
      ]);
      const parsed = bankConnectionsResponseSchema.parse(cards);
      setConnections(parsed.connections);
      setObStatus(openBankingConfigStatusSchema.parse(statusResponse));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not load your bank connections. Try again shortly.",
      );
    } finally {
      setLoading(false);
    }
  }, [user]);

  const finalizeConnection = useCallback(
    async (lookup: string, code: string | null) => {
      setBusyId("finalize");
      setMessage(null);
      setError(null);
      try {
        const payload: Record<string, string> = searchParams.get("state")
          ? { state: lookup }
          : { reference: lookup };
        if (code) payload.code = code;
        const data = await apiClient.post<unknown>(
          "/finance/integrations/open-banking/finalize",
          payload,
        );
        const result = openBankingSyncResultSchema.parse(data);
        setMessage(result.message || "Connected successfully.");
        await load();
        router.replace("/finance/connect");
      } catch (err) {
        setError(mapOpenBankingConnectError(err));
      } finally {
        setBusyId(null);
      }
    },
    [load, router, searchParams],
  );

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!writable) return;
    const callback = searchParams.get("open_banking");
    const lookup = searchParams.get("state") || searchParams.get("ref");
    const code = searchParams.get("code");
    if (callback === "callback" && lookup) {
      void finalizeConnection(lookup, code);
    }
  }, [writable, searchParams, finalizeConnection]);

  async function connectOpenBanking(connectionId: string) {
    if (!obConfigured) {
      setError("Open Banking is not set up yet. Complete Open Banking Setup first.");
      return;
    }
    if (obNeedsActivation) {
      setError(mapOpenBankingConnectError(new Error(obStatus?.readiness_message ?? "not active")));
      return;
    }
    const query = CONNECTION_SEARCH[connectionId];
    if (!query) return;

    setBusyId(connectionId);
    setError(null);
    setMessage(null);
    try {
      const data = await apiClient.get<unknown>(
        `/finance/integrations/open-banking/institutions?country=gb&q=${encodeURIComponent(query)}`,
      );
      const rows = z.array(openBankingInstitutionSchema).parse(data);
      const institution =
        rows.find((row) => row.name.toLowerCase().includes(query.toLowerCase())) ?? rows[0];
      if (!institution) {
        setError("Unsupported institution — this bank is not available from your provider right now.");
        return;
      }
      const connectData = await apiClient.post<unknown>("/finance/integrations/open-banking/connect", {
        institution_id: institution.id,
        institution_name: institution.name,
      });
      const result = openBankingConnectResponseSchema.parse(connectData);
      setMessage(`Taking you to ${result.institution_name} to sign in…`);
      window.location.href = result.link;
    } catch (err) {
      setError(mapOpenBankingConnectError(err));
    } finally {
      setBusyId(null);
    }
  }

  async function syncConnection(connectionId: string) {
    setBusyId(connectionId);
    setError(null);
    setMessage(null);
    try {
      const data = await apiClient.post<unknown>(`/finance/bank-connections/${connectionId}/sync`);
      const result = openBankingSyncResultSchema.parse(data);
      setMessage(result.message || "Sync complete.");
      await load();
    } catch {
      setError("Daily sync failed. Try Sync now again in a few minutes.");
    } finally {
      setBusyId(null);
    }
  }

  async function disconnectConnection(connectionId: string) {
    setBusyId(connectionId);
    setError(null);
    try {
      await apiClient.post(`/finance/bank-connections/${connectionId}/disconnect`);
      setMessage("Disconnected. You can connect again any time.");
      await load();
    } catch {
      setError("Could not disconnect. Try again.");
    } finally {
      setBusyId(null);
    }
  }

  function handleConnect(connection: BankConnectionItem) {
    if (connection.method === "open_banking") {
      void connectOpenBanking(connection.id);
      return;
    }
    if (connection.method === "quickfile") {
      void syncConnection(connection.id);
    }
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-[var(--muted)]">
        Connect your accounts once — balances and transactions refresh automatically every day. You
        only ever log in on your bank&apos;s own secure page.
      </p>

      {!obConfigured ? (
        <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm">
          Before connecting personal banks, an admin needs to complete{" "}
          <Link href="/finance/open-banking/settings" className="font-medium underline">
            Open Banking Settings
          </Link>{" "}
          once.
        </p>
      ) : null}

      {obNeedsActivation ? (
        <section className="rounded-xl border border-amber-300/40 bg-amber-500/10 px-4 py-4 text-sm text-amber-950 dark:text-amber-100">
          <h2 className="font-semibold">Open Banking activation required</h2>
          <p className="mt-2">
            {obStatus?.readiness_message ??
              "Your provider accepted the credentials but the app is not fully active yet."}
          </p>
          <p className="mt-2 rounded-lg border border-amber-400/30 bg-amber-500/5 px-3 py-2">
            <strong>UK banks (Lloyds, MBNA, Virgin):</strong> your Enable Banking account currently
            lists <strong>zero GB banks</strong>, so those cannot be connected via Enable Banking.
            For UK personal accounts, switch provider to{" "}
            <strong>GoCardless / Nordigen</strong> in{" "}
            <Link href="/finance/open-banking/settings" className="font-medium underline">
              Open Banking Settings
            </Link>{" "}
            (free Bank Account Data tier).
          </p>
          <ol className="mt-3 list-decimal space-y-1 pl-5">
            <li>
              Sign in at{" "}
              <a
                href="https://enablebanking.com/sign-in/?next=%2Fcp%2Fapplications"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium underline"
              >
                Enable Banking Control Panel
              </a>{" "}
              using <strong>robertdavidcashman@gmail.com</strong> (magic link — not AOL)
            </li>
            <li>Open <strong>Rob&apos;s Finance Production</strong> → Activate by linking accounts</li>
            <li>Return here and press Connect on each bank (or use GoCardless for UK banks)</li>
          </ol>
          <div className="mt-3 flex flex-wrap gap-2">
            <a
              href={ENABLE_BANKING_CP_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="solar-btn-primary text-sm"
            >
              Open Enable Banking CP
            </a>
            <Link href="/finance/open-banking/settings" className="solar-btn-secondary text-sm">
              Open Banking Settings
            </Link>
          </div>
        </section>
      ) : null}

      {message ? (
        <p className="rounded-lg border border-emerald-300/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-900 dark:text-emerald-200">
          {message}
        </p>
      ) : null}

      {error ? (
        <p className="rounded-lg border border-red-300/40 bg-red-500/10 px-3 py-2 text-sm text-red-800 dark:text-red-200">
          {error}
        </p>
      ) : null}

      {loading ? (
        <p className="text-sm text-[var(--muted)]">Loading connections…</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {connections.map((connection) => (
            <BankConnectionCard
              key={connection.id}
              connection={connection}
              writable={writable}
              busy={busyId === connection.id || busyId === "finalize"}
              onConnect={() => handleConnect(connection)}
              onDisconnect={() => void disconnectConnection(connection.id)}
              onSync={() => void syncConnection(connection.id)}
            />
          ))}
        </div>
      )}

      {busyId === "finalize" ? (
        <p className="text-sm text-[var(--muted)]">Completing bank connection…</p>
      ) : null}
    </div>
  );
}
