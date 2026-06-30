"use client";

import { useEffect, useRef, useState } from "react";

import { summariseApplyResult } from "@/lib/ai-apply";
import { apiClient, ApiError } from "@/lib/api-client";
import {
  aiAssessmentSchema,
  aiChatResponseSchema,
  aiStatusSchema,
  type AiAssessment,
  type AiProposedAction,
  type AiStatus,
} from "@/lib/schemas";

type ChatTurn = {
  role: "user" | "assistant";
  content: string;
  actions?: AiProposedAction[];
};

const ACTION_LABELS: Record<AiProposedAction["kind"], string> = {
  set_tou_bands: "Update charge schedule",
  set_export_limit: "Set export limit",
  set_operating_mode: "Set operating mode",
  set_auto_schedule: "Update auto-align",
};

export function AssistantPanel() {
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [assessment, setAssessment] = useState<AiAssessment | null>(null);
  const [assessing, setAssessing] = useState(false);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [applied, setApplied] = useState<Record<string, string>>({});
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setStatus(aiStatusSchema.parse(await apiClient.get("/ai/status")));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load AI status");
      }
    })();
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  const runAssessment = async () => {
    setError(null);
    setAssessing(true);
    try {
      setAssessment(aiAssessmentSchema.parse(await apiClient.post("/ai/assess")));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Assessment failed");
    } finally {
      setAssessing(false);
    }
  };

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || sending) {
      return;
    }
    setError(null);
    setSending(true);
    const history = [...turns, { role: "user" as const, content: text }];
    setTurns(history);
    setInput("");
    try {
      const reply = aiChatResponseSchema.parse(
        await apiClient.post("/ai/chat", {
          messages: history.map((t) => ({ role: t.role, content: t.content })),
        }),
      );
      setTurns((prev) => [
        ...prev,
        { role: "assistant", content: reply.reply, actions: reply.proposed_actions },
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Chat failed");
    } finally {
      setSending(false);
    }
  };

  const applyAction = async (action: AiProposedAction, key: string) => {
    setError(null);
    setApplied((prev) => ({ ...prev, [key]: "applying" }));
    try {
      const raw = await apiClient.post(action.endpoint, action.body);
      setApplied((prev) => ({ ...prev, [key]: summariseApplyResult(action, raw) }));
    } catch (e) {
      const msg =
        e instanceof ApiError ? `${e.message} (HTTP ${e.status})` : "Failed to apply change";
      setApplied((prev) => ({ ...prev, [key]: msg }));
    }
  };

  const renderActions = (actions: AiProposedAction[] | undefined, scope: string) => {
    if (!actions || actions.length === 0) {
      return null;
    }
    return (
      <div className="mt-3 space-y-3">
        {actions.map((action, idx) => {
          const key = `${scope}-${idx}`;
          const state = applied[key];
          return (
            <div key={key} className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3">
              <p className="text-sm font-semibold">{ACTION_LABELS[action.kind] ?? action.kind}</p>
              <p className="mt-0.5 text-sm">{action.summary}</p>
              {action.reason ? (
                <p className="mt-1 text-xs text-[var(--muted)]">Why: {action.reason}</p>
              ) : null}
              <pre className="mt-2 overflow-x-auto rounded bg-[var(--surface-elevated)] p-2 text-xs text-[var(--muted)]">
                {JSON.stringify(action.body, null, 2)}
              </pre>
              <div className="mt-2 flex items-center gap-3">
                <button
                  type="button"
                  className="solar-btn-primary text-xs"
                  disabled={state === "applying" || (state?.startsWith("Applied") ?? false)}
                  onClick={() => void applyAction(action, key)}
                >
                  {state === "applying" ? "Applying…" : "Confirm & apply"}
                </button>
                {state && state !== "applying" ? (
                  <span
                    className={`text-xs ${state.startsWith("Applied") ? "text-emerald-500" : "text-red-500"}`}
                  >
                    {state}
                  </span>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  if (status && !status.enabled) {
    return (
      <div className="solar-card">
        <p className="text-sm font-semibold">AI assistant is not configured</p>
        <p className="mt-1 text-sm text-[var(--muted)]">{status.reason}</p>
        <p className="mt-2 text-xs text-[var(--muted)]">
          Set <code>OPENAI_API_KEY</code> and <code>AI_ENABLED=true</code> in the backend
          environment, then restart the backend.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error ? (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-500">
          {error}
        </div>
      ) : null}

      <div className="solar-card">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold">Are my settings optimal right now?</p>
            <p className="text-xs text-[var(--muted)]">
              The assistant reads live metrics, tariff, and your schedule, then proposes changes you
              confirm.
            </p>
          </div>
          <button
            type="button"
            className="solar-btn-primary text-sm"
            disabled={assessing}
            onClick={() => void runAssessment()}
          >
            {assessing ? "Analysing…" : "Assess now"}
          </button>
        </div>

        {assessment ? (
          <div className="mt-4">
            <div className="flex items-center gap-2">
              <span
                className={`inline-flex h-2.5 w-2.5 rounded-full ${assessment.optimal ? "bg-emerald-400" : "bg-amber-400"}`}
              />
              <p className="text-sm font-semibold">{assessment.headline}</p>
            </div>
            {assessment.findings.length > 0 ? (
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-[var(--muted)]">
                {assessment.findings.map((f, i) => (
                  <li key={i}>{f}</li>
                ))}
              </ul>
            ) : null}
            {renderActions(assessment.proposed_actions, "assess")}
          </div>
        ) : null}
      </div>

      <div className="solar-card">
        <p className="text-sm font-semibold">Ask a question</p>
        <div className="mt-3 max-h-96 space-y-3 overflow-y-auto">
          {turns.length === 0 ? (
            <p className="text-sm text-[var(--muted)]">
              e.g. &ldquo;Why is the grid importing when the battery is at 96%?&rdquo;
            </p>
          ) : null}
          {turns.map((turn, idx) => (
            <div
              key={idx}
              className={turn.role === "user" ? "flex justify-end" : "flex justify-start"}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${
                  turn.role === "user"
                    ? "bg-gradient-to-r from-amber-500 to-orange-500 text-white"
                    : "bg-[var(--surface)] text-[var(--foreground)]"
                }`}
              >
                <p className="whitespace-pre-wrap">{turn.content}</p>
                {turn.role === "assistant" ? renderActions(turn.actions, `chat-${idx}`) : null}
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </div>
        <form
          className="mt-3 flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void sendMessage();
          }}
        >
          <input
            className="solar-input flex-1"
            placeholder="Ask about your solar settings…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={sending}
          />
          <button type="submit" className="solar-btn-primary text-sm" disabled={sending || !input.trim()}>
            {sending ? "…" : "Send"}
          </button>
        </form>
      </div>
    </div>
  );
}
