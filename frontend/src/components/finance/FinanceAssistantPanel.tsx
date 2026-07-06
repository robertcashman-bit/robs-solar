"use client";

import { FormEvent, useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import {
  financeAiChatResponseSchema,
  financeAiStatusSchema,
  type FinanceAiChatMessage,
  type FinanceAiStatus,
} from "@/lib/finance-schemas";

type FinanceAssistantPanelProps = {
  canUse: boolean;
};

export function FinanceAssistantPanel({ canUse }: FinanceAssistantPanelProps) {
  const [status, setStatus] = useState<FinanceAiStatus | null>(null);
  const [messages, setMessages] = useState<FinanceAiChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!canUse) return;
    void (async () => {
      try {
        setStatus(financeAiStatusSchema.parse(await apiClient.get("/finance/ai/status")));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load finance AI");
      }
    })();
  }, [canUse]);

  if (!canUse) {
    return <p className="text-sm text-[var(--muted)]">Admin access required.</p>;
  }

  if (status && !status.enabled) {
    return <p className="text-sm text-[var(--muted)]">{status.reason}</p>;
  }

  const send = async (event: FormEvent) => {
    event.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    const nextMessages: FinanceAiChatMessage[] = [...messages, { role: "user", content: text }];
    setMessages(nextMessages);
    setInput("");
    setBusy(true);
    setError(null);
    try {
      const data = financeAiChatResponseSchema.parse(
        await apiClient.post("/finance/ai/chat", { messages: nextMessages }),
      );
      setMessages([...nextMessages, { role: "assistant", content: data.reply }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Chat failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="min-h-[280px] space-y-3 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
        {messages.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">
            Ask about cash flow, debt payoff, QuickFile profit, or whether historic (H) fields need
            updating after Open Banking sync.
          </p>
        ) : null}
        {messages.map((m, i) => (
          <div
            key={`${m.role}-${i}`}
            className={`rounded-xl px-3 py-2 text-sm ${
              m.role === "user"
                ? "ml-8 bg-emerald-500/10"
                : "mr-8 border border-[var(--border)] bg-[var(--surface-elevated)]"
            }`}
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
              {m.role}
            </p>
            <p className="mt-1 whitespace-pre-wrap">{m.content}</p>
          </div>
        ))}
      </div>
      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}
      <form onSubmit={(e) => void send(e)} className="flex gap-2">
        <input
          className="solar-input flex-1"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a finance question…"
          disabled={busy}
        />
        <button type="submit" className="solar-btn-primary" disabled={busy || !input.trim()}>
          {busy ? "…" : "Send"}
        </button>
      </form>
    </div>
  );
}
