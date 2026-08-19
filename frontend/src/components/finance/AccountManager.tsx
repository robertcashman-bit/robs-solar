"use client";

import { useState } from "react";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { apiClient } from "@/lib/api-client";
import { notifyFinanceChanged } from "@/lib/finance-events";
import { accountUsesCreditLimit, moneyFieldValue, requiredMoney } from "@/lib/finance-form";
import type { FinanceAccount } from "@/lib/finance-schemas";
import { formatGbp } from "@/lib/money";

type AccountTypeOption = { value: string; label: string };

type AccountManagerProps = {
  scope: "personal" | "business";
  accounts: FinanceAccount[];
  types: AccountTypeOption[];
  canEdit: boolean;
  /** When true, suppress the empty-state copy so first paint is not a fake void. */
  loading?: boolean;
  onChanged: () => Promise<void>;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
};

export function AccountManager({
  scope,
  accounts,
  types,
  canEdit,
  loading = false,
  onChanged,
  onError,
  onNotice,
}: AccountManagerProps) {
  const [form, setForm] = useState({
    name: "",
    balance_gbp: "",
    account_type: types[0]?.value ?? "current",
    credit_limit_gbp: "",
    dla_direction: "company_owes_director",
  });
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({
    name: "",
    balance_gbp: "",
    credit_limit_gbp: "",
    dla_direction: "company_owes_director",
  });
  const [saving, setSaving] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<FinanceAccount | null>(null);

  async function addAccount(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || saving) return;
    setSaving(true);
    try {
      await apiClient.post("/finance/accounts", {
        scope,
        account_type: form.account_type,
        name: form.name.trim(),
        balance_gbp: requiredMoney(form.balance_gbp, "balance"),
        credit_limit_gbp:
          accountUsesCreditLimit(form.account_type) && form.credit_limit_gbp.trim()
            ? requiredMoney(form.credit_limit_gbp, "credit limit")
            : null,
        dla_direction: form.account_type === "directors_loan" ? form.dla_direction : null,
      });
      setForm({
        name: "",
        balance_gbp: "",
        account_type: types[0]?.value ?? "current",
        credit_limit_gbp: "",
        dla_direction: "company_owes_director",
      });
      onNotice("Account saved.");
      await onChanged();
      notifyFinanceChanged();
    } catch (err) {
      onError(err instanceof Error ? err.message : "The account could not be saved. Existing data is unchanged.");
    } finally {
      setSaving(false);
    }
  }

  async function saveEdit(account: FinanceAccount) {
    if (!canEdit || saving) return;
    const name = editForm.name.trim();
    if (!name) {
      onError("Account name is required.");
      return;
    }
    setSaving(true);
    try {
      await apiClient.put(`/finance/accounts/${account.id}`, {
        name,
        balance_gbp: requiredMoney(editForm.balance_gbp, "balance"),
        credit_limit_gbp:
          accountUsesCreditLimit(account.account_type) && editForm.credit_limit_gbp.trim()
            ? requiredMoney(editForm.credit_limit_gbp, "credit limit")
            : accountUsesCreditLimit(account.account_type)
              ? null
              : undefined,
        dla_direction: account.account_type === "directors_loan" ? editForm.dla_direction : undefined,
      });
      setEditingId(null);
      onNotice("Account updated.");
      await onChanged();
      notifyFinanceChanged();
    } catch (err) {
      onError(err instanceof Error ? err.message : "The account could not be updated. Existing data is unchanged.");
    } finally {
      setSaving(false);
    }
  }

  async function confirmDelete() {
    if (!pendingDelete || saving) return;
    setSaving(true);
    try {
      await apiClient.delete(`/finance/accounts/${pendingDelete.id}`);
      onNotice("Account removed from active totals.");
      setPendingDelete(null);
      await onChanged();
      notifyFinanceChanged();
    } catch (err) {
      onError(err instanceof Error ? err.message : "The account could not be removed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <ul className="mt-3 space-y-2">
        {accounts.map((account) => (
          <li
            key={account.id}
            className="flex flex-col gap-2 rounded-xl border border-[var(--border)] px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between"
          >
            <span>
              {account.name}{" "}
              <span className="text-[var(--muted)]">({account.account_type.replaceAll("_", " ")})</span>
              {account.credit_limit_gbp ? (
                <span className="text-[var(--muted)]">
                  {" "}
                  · limit {formatGbp(account.credit_limit_gbp)}
                </span>
              ) : accountUsesCreditLimit(account.account_type) ? (
                <span className="text-[var(--muted)]"> · add a credit limit for available credit</span>
              ) : null}
              {account.account_type === "directors_loan" ? (
                <span className="text-[var(--muted)]">
                  {" "}
                  ·{" "}
                  {account.dla_direction === "director_owes_company"
                    ? "Robert owes the company"
                    : "company owes Robert"}
                </span>
              ) : null}
            </span>
            {editingId === account.id ? (
              <form
                className="flex flex-wrap items-end gap-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  void saveEdit(account);
                }}
              >
                <label className="space-y-1 text-xs">
                  <span>Name</span>
                  <input
                    className="solar-input w-40"
                    value={editForm.name}
                    onChange={(event) => setEditForm({ ...editForm, name: event.target.value })}
                    required
                  />
                </label>
                <label className="space-y-1 text-xs">
                  <span>Balance (£)</span>
                  <input
                    className="solar-input w-28"
                    inputMode="decimal"
                    value={editForm.balance_gbp}
                    onChange={(event) => setEditForm({ ...editForm, balance_gbp: event.target.value })}
                    required
                  />
                </label>
                {accountUsesCreditLimit(account.account_type) ? (
                  <label className="space-y-1 text-xs">
                    <span>Credit limit (£)</span>
                    <input
                      className="solar-input w-28"
                      inputMode="decimal"
                      value={editForm.credit_limit_gbp}
                      onChange={(event) => setEditForm({ ...editForm, credit_limit_gbp: event.target.value })}
                    />
                  </label>
                ) : null}
                {account.account_type === "directors_loan" ? (
                  <label className="space-y-1 text-xs">
                    <span>Direction</span>
                    <select
                      className="solar-input w-56"
                      value={editForm.dla_direction}
                      onChange={(event) => setEditForm({ ...editForm, dla_direction: event.target.value })}
                    >
                      <option value="director_owes_company">Robert owes the company</option>
                      <option value="company_owes_director">Company owes Robert</option>
                    </select>
                  </label>
                ) : null}
                <button type="submit" className="solar-btn-primary text-xs" disabled={saving}>
                  Save
                </button>
                <button type="button" className="solar-btn-ghost text-xs" onClick={() => setEditingId(null)}>
                  Cancel
                </button>
              </form>
            ) : (
              <div className="flex items-center gap-3">
                <span className="font-semibold tabular-nums">{formatGbp(account.balance_gbp)}</span>
                {canEdit ? (
                  <>
                    <button
                      type="button"
                      className="solar-btn-ghost text-xs"
                      onClick={() => {
                        setEditingId(account.id);
                        setEditForm({
                          name: account.name,
                          balance_gbp: moneyFieldValue(account.balance_gbp),
                          credit_limit_gbp: moneyFieldValue(account.credit_limit_gbp),
                          dla_direction: account.dla_direction ?? "company_owes_director",
                        });
                      }}
                    >
                      Edit
                    </button>
                    <button type="button" className="solar-btn-ghost text-xs" onClick={() => setPendingDelete(account)}>
                      Archive
                    </button>
                  </>
                ) : null}
              </div>
            )}
          </li>
        ))}
        {loading ? (
          <li className="rounded-xl border border-dashed border-[var(--border)] px-4 py-6 text-sm text-[var(--muted)]">
            Loading accounts…
          </li>
        ) : accounts.length === 0 ? (
          <li className="rounded-xl border border-dashed border-[var(--border)] px-4 py-6 text-sm text-[var(--muted)]">
            No {scope === "business" ? "company" : scope} accounts yet. Add a current account so Overview cash totals stay accurate.
          </li>
        ) : null}
      </ul>
      {canEdit ? (
        <form onSubmit={(event) => void addAccount(event)} className="mt-6 grid gap-3 rounded-2xl border border-[var(--border)] p-4 sm:grid-cols-2 lg:grid-cols-5">
          <label className="space-y-1 text-sm sm:col-span-1">
            <span>Account name</span>
            <input
              className="solar-input"
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              required
            />
          </label>
          <label className="space-y-1 text-sm">
            <span>Type</span>
            <select
              className="solar-input"
              value={form.account_type}
              onChange={(event) => setForm({ ...form, account_type: event.target.value })}
            >
              {types.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-sm">
            <span>Balance (£)</span>
            <input
              className="solar-input"
              inputMode="decimal"
              placeholder="0.00"
              value={form.balance_gbp}
              onChange={(event) => setForm({ ...form, balance_gbp: event.target.value })}
              required
            />
          </label>
          {accountUsesCreditLimit(form.account_type) ? (
            <label className="space-y-1 text-sm">
              <span>Credit limit (£)</span>
              <input
                className="solar-input"
                inputMode="decimal"
                placeholder="Needed for available credit"
                value={form.credit_limit_gbp}
                onChange={(event) => setForm({ ...form, credit_limit_gbp: event.target.value })}
              />
            </label>
          ) : null}
          {form.account_type === "directors_loan" ? (
            <label className="space-y-1 text-sm">
              <span>Direction</span>
              <select
                className="solar-input"
                value={form.dla_direction}
                onChange={(event) => setForm({ ...form, dla_direction: event.target.value })}
              >
                <option value="director_owes_company">Robert owes the company</option>
                <option value="company_owes_director">Company owes Robert</option>
              </select>
            </label>
          ) : null}
          <button type="submit" className="solar-btn-primary self-end" disabled={saving}>
            {saving ? "Saving…" : "Add account"}
          </button>
        </form>
      ) : null}
      <ConfirmDialog
        open={pendingDelete != null}
        title="Archive this account?"
        description="It will leave active totals. Historical snapshots are unchanged."
        confirmLabel="Archive"
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => void confirmDelete()}
      />
    </>
  );
}
