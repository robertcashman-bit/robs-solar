"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { summariseApplyResult } from "@/lib/ai-apply";
import { apiClient, ApiError } from "@/lib/api-client";
import {
  aiAssessmentSchema,
  aiStatusSchema,
  type AiAssessment,
  type AiProposedAction,
  type AiStatus,
} from "@/lib/schemas";
import { BoltIcon } from "@/components/shared/icons";

const ACTION_LABELS: Record<AiProposedAction["kind"], string> = {
  set_tou_bands: "Update charge schedule",
  set_export_limit: "Set export limit",
  set_operating_mode: "Set operating mode",
  set_auto_schedule: "Update auto-align",
};

type AiAdviceCardProps = {
  canControl: boolean;
};

export function AiAdviceCard({ canControl }: AiAdviceCardProps) {
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [assessment, setAssessment] = useState<AiAssessment | null>(null);
  const [assessing, setAssessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [applied, setApplied] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!canControl) return;
    void (async () => {
      try {
        setStatus(aiStatusSchema.parse(await apiClient.get("/ai/status")));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load AI status");
      }
    })();
  }, [canControl]);

  if (!canControl) {
    return null;
  }

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

  const applyAction = async (action: AiProposedAction, key: string) => {
    setApplied((prev) => ({ ...prev, [key]: "applying" }));
    try {
      const raw = await apiClient.post(action.endpoint, action.body);
      setApplied((prev) => ({
        ...prev,
        [key]: summariseApplyResult(action, raw),
      }));
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Failed to apply";
      setApplied((prev) => ({ ...prev, [key]: msg }));
    }
  };

  if (status && !status.enabled) {
    return (
      <section aria-label="AI advice" className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-violet-500/15 text-violet-600 dark:text-violet-300">
            <BoltIcon size={18} />
          </span>
          <div>
            <p className="text-sm font-semibold">AI assistant not configured</p>
            <p className="mt-0.5 text-sm text-[var(--muted)]">{status.reason}</p>
            <p className="mt-2 text-xs text-[var(--muted)]">
              Log in as <strong>admin</strong> and set <code>AI_ENABLED=true</code> plus{" "}
              <code>OPENAI_API_KEY</code> on the backend, then redeploy.
            </p>
          </div>
        </div>
      </section>
    );
  }

  const topAction = assessment?.proposed_actions?.[0];

  return (
    <section
      aria-label="AI advice"
      className="rounded-2xl border border-violet-300/40 bg-gradient-to-br from-violet-500/10 to-[var(--surface)] p-4 dark:border-violet-800/40"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-violet-500/20 text-violet-600 dark:text-violet-300">
            <BoltIcon size={18} />
          </span>
          <div>
            <p className="text-sm font-semibold">AI settings check</p>
            <p className="mt-0.5 text-sm text-[var(--muted)]">
              Ask whether your schedule and battery settings are optimal right now.
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            className="solar-btn-primary text-sm"
            disabled={assessing}
            onClick={() => void runAssessment()}
          >
            {assessing ? "Checking…" : "Get AI advice"}
          </button>
          <Link href="/energy/assistant" className="solar-btn-ghost text-sm">
            Full assistant →
          </Link>
        </div>
      </div>

      {error ? <p className="mt-3 text-sm text-red-500">{error}</p> : null}

      {assessment ? (
        <div className="mt-4 space-y-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
          <p className="text-sm font-semibold">{assessment.headline}</p>
          {assessment.findings.slice(0, 2).map((finding) => (
            <p key={finding} className="text-sm text-[var(--muted)]">
              • {finding}
            </p>
          ))}
          {topAction ? (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] p-3">
              <p className="text-sm font-medium">
                {ACTION_LABELS[topAction.kind] ?? topAction.kind}
              </p>
              <p className="mt-0.5 text-sm text-[var(--muted)]">{topAction.summary}</p>
              <button
                type="button"
                className="solar-btn-primary mt-2 text-xs"
                disabled={applied["top"] === "applying"}
                onClick={() => void applyAction(topAction, "top")}
              >
                {applied["top"] === "applying" ? "Applying…" : "Confirm & apply"}
              </button>
              {applied["top"] && applied["top"] !== "applying" ? (
                <p className="mt-1 text-xs text-[var(--muted)]">{applied["top"]}</p>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
