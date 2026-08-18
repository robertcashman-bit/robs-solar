"use client";

import { useMemo, useState } from "react";

import { apiClient } from "@/lib/api-client";

export type CategoryOption = {
  parent: string;
  scope: string;
};

type TransactionCategoryEditorProps = {
  txnId: number;
  scope: string;
  category: string;
  categoryConfidence?: string;
  options: CategoryOption[];
  canEdit: boolean;
  disabled?: boolean;
  onUpdated: (next: { category: string; category_confidence?: string }) => void;
  onError: (message: string) => void;
};

export function TransactionCategoryEditor({
  txnId,
  scope,
  category,
  categoryConfidence,
  options,
  canEdit,
  disabled = false,
  onUpdated,
  onError,
}: TransactionCategoryEditorProps) {
  const [editing, setEditing] = useState(false);
  const [mode, setMode] = useState<"pick" | "new">("pick");
  const [draft, setDraft] = useState(category || "");
  const [busy, setBusy] = useState(false);

  const scopedNames = useMemo(() => {
    const names = [
      ...new Set(
        options
          .filter((item) => !item.scope || item.scope === scope)
          .map((item) => item.parent)
          .filter(Boolean),
      ),
    ].sort((a, b) => a.localeCompare(b));
    if (category && !names.includes(category)) {
      names.unshift(category);
    }
    return names;
  }, [options, scope, category]);

  if (!canEdit) {
    return (
      <span>
        {category || "—"}
        {categoryConfidence ? (
          <span className="ml-1 text-xs text-[var(--muted)]">{categoryConfidence}</span>
        ) : null}
      </span>
    );
  }

  const openEditor = () => {
    setDraft(category || scopedNames[0] || "");
    setMode("pick");
    setEditing(true);
  };

  const cancel = () => {
    setEditing(false);
    setMode("pick");
    setDraft(category || "");
  };

  const save = async () => {
    const next = draft.trim();
    if (!next) {
      onError("Enter a category name");
      return;
    }
    if (next === category) {
      setEditing(false);
      return;
    }
    setBusy(true);
    try {
      const result = await apiClient.post<{
        category: string;
        category_confidence?: string;
      }>(`/finance/transactions/${txnId}/category`, { category: next });
      onUpdated({
        category: result.category,
        category_confidence: result.category_confidence,
      });
      setEditing(false);
      setMode("pick");
    } catch (err) {
      onError(err instanceof Error ? err.message : "Could not update category");
    } finally {
      setBusy(false);
    }
  };

  if (!editing) {
    return (
      <button
        type="button"
        className="max-w-[12rem] rounded-md px-1 py-0.5 text-left hover:bg-[var(--border)]/40 focus:outline-none focus:ring-2 focus:ring-emerald-600/40"
        onClick={openEditor}
        disabled={disabled}
        aria-label={`Edit category for transaction ${txnId}`}
      >
        <span className="font-medium">{category || "Set category"}</span>
        {categoryConfidence ? (
          <span className="ml-1 text-xs text-[var(--muted)]">{categoryConfidence}</span>
        ) : null}
      </button>
    );
  }

  return (
    <div className="flex min-w-[11rem] max-w-[16rem] flex-col gap-1.5 sm:min-w-[13rem]">
      {mode === "pick" ? (
        <select
          className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-sm"
          value={scopedNames.includes(draft) ? draft : ""}
          onChange={(event) => {
            if (event.target.value === "__new__") {
              setMode("new");
              setDraft("");
              return;
            }
            setDraft(event.target.value);
          }}
          disabled={busy || disabled}
          aria-label="Choose category"
        >
          {!scopedNames.includes(draft) && draft ? (
            <option value={draft}>{draft}</option>
          ) : null}
          {scopedNames.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
          <option value="__new__">Add new category…</option>
        </select>
      ) : (
        <input
          className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-sm"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="New category name"
          disabled={busy || disabled}
          aria-label="New category name"
          autoFocus
        />
      )}
      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          className="rounded-md bg-emerald-600 px-2 py-1 text-xs text-white disabled:opacity-50"
          disabled={busy || disabled || !draft.trim()}
          onClick={() => void save()}
        >
          {busy ? "Saving…" : "Save"}
        </button>
        <button
          type="button"
          className="rounded-md border border-[var(--border)] px-2 py-1 text-xs disabled:opacity-50"
          disabled={busy || disabled}
          onClick={cancel}
        >
          Cancel
        </button>
        {mode === "new" ? (
          <button
            type="button"
            className="rounded-md border border-[var(--border)] px-2 py-1 text-xs disabled:opacity-50"
            disabled={busy || disabled}
            onClick={() => {
              setMode("pick");
              setDraft(category || scopedNames[0] || "");
            }}
          >
            Pick existing
          </button>
        ) : null}
      </div>
    </div>
  );
}
