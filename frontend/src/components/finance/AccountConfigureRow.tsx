"use client";

import { useState } from "react";

import { FinanceAmount } from "@/components/finance/FinanceAmount";
import { apiClient } from "@/lib/api-client";
import {
  financeAccountSchema,
  financeAccountTypeSchema,
  type FinanceAccount,
} from "@/lib/finance-schemas";
import { financeRoleForAccountBalance } from "@/lib/money";

const ACCOUNT_TYPES = financeAccountTypeSchema.options;

type AccountConfigureRowProps = {
  account: FinanceAccount;
  onSaved: (account: FinanceAccount) => void;
  readOnly?: boolean;
};

export function AccountConfigureRow({
  account,
  onSaved,
  readOnly = false,
}: AccountConfigureRowProps) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(account.name);
  const [accountType, setAccountType] = useState(account.account_type);
  const [notes, setNotes] = useState(account.notes);
  const [balance, setBalance] = useState(String(account.balance_gbp));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const isManual = account.source === "manual";
      const data = await apiClient.put<unknown>(`/finance/accounts/${account.id}`, {
        name: name.trim(),
        account_type: accountType,
        notes,
        ...(isManual ? { balance_gbp: Number(balance) } : {}),
      });
      const updated = financeAccountSchema.parse(data);
      onSaved(updated);
      setOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save account");
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="rounded-xl border border-[var(--border)] px-4 py-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium">{account.name}</p>
          <p className="text-xs text-[var(--muted)]">
            {account.scope} · {account.account_type.replaceAll("_", " ")} · {account.source}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <FinanceAmount
            value={account.balance_gbp}
            role={financeRoleForAccountBalance(account.account_type, account.balance_gbp)}
          />
          {!readOnly ? (
            <button
              type="button"
              className="solar-btn-ghost text-xs"
              onClick={() => setOpen((value) => !value)}
            >
              {open ? "Close" : "Configure"}
            </button>
          ) : null}
        </div>
      </div>

      {open ? (
        <div className="mt-3 grid gap-3 border-t border-[var(--border)] pt-3 sm:grid-cols-2">
          <label className="block text-xs sm:col-span-2">
            <span className="mb-1 block text-[var(--muted)]">Display name</span>
            <input
              className="solar-input w-full"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label className="block text-xs">
            <span className="mb-1 block text-[var(--muted)]">Account type</span>
            <select
              className="solar-input w-full"
              value={accountType}
              onChange={(e) => setAccountType(e.target.value as FinanceAccount["account_type"])}
            >
              {ACCOUNT_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>
          {account.source === "manual" ? (
            <label className="block text-xs">
              <span className="mb-1 block text-[var(--muted)]">Balance (GBP)</span>
              <input
                className="solar-input w-full"
                type="number"
                step="0.01"
                value={balance}
                onChange={(e) => setBalance(e.target.value)}
              />
            </label>
          ) : (
            <p className="self-end text-xs text-[var(--muted)]">
              Balance syncs from {account.provider || account.source}.
            </p>
          )}
          <label className="block text-xs sm:col-span-2">
            <span className="mb-1 block text-[var(--muted)]">Notes</span>
            <input
              className="solar-input w-full"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </label>
          {error ? (
            <p className="text-xs text-red-600 dark:text-red-400 sm:col-span-2">{error}</p>
          ) : null}
          <button
            type="button"
            className="solar-btn-primary text-sm sm:col-span-2 sm:max-w-xs"
            disabled={busy || !name.trim()}
            onClick={() => void save()}
          >
            {busy ? "Saving…" : "Save account"}
          </button>
        </div>
      ) : null}
    </li>
  );
}
