"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { z } from "zod";

import { BankConnectionCard } from "@/components/finance/BankConnectionCard";
import { CONNECTION_SEARCH } from "@/lib/bank-connections";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import {
  bankConnectionsResponseSchema,
  openBankingConfigStatusSchema,
  openBankingConnectResponseSchema,
  openBankingInstitutionSchema,
  openBankingSyncResultSchema,
  type BankConnectionItem,
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
  const [obConfigured, setObConfigured] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const [cards, obStatus] = await Promise.all([
        apiClient.get<unknown>("/finance/bank-connections"),
        apiClient.get<unknown>("/finance/integrations/open-banking/status"),
      ]);
      const parsed = bankConnectionsResponseSchema.parse(cards);
      setConnections(parsed.connections);
      setObConfigured(openBankingConfigStatusSchema.parse(obStatus).configured);
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
      } catch {
        setError("Bank requires reconnection. Press Connect and sign in again at your bank.");
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
    } catch {
      setError("Provider unavailable. Try again later or check Open Banking Settings.");
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
