"use client";

import { useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import {
  automationRuleSchema,
  automationRulesResponseSchema,
  type AutomationRule,
} from "@/lib/schemas";

type RulesPanelProps = {
  disabled?: boolean;
};

export function RulesPanel({ disabled = false }: RulesPanelProps) {
  const [rules, setRules] = useState<AutomationRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("SOC low alert");
  const [condition, setCondition] = useState("soc_below");
  const [conditionValue, setConditionValue] = useState("20");
  const [action, setAction] = useState("raise_alert");

  const refresh = async () => {
    const data = automationRulesResponseSchema.parse(await apiClient.get("/controls/rules"));
    setRules(data.rules);
  };

  useEffect(() => {
    void (async () => {
      try {
        await refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load rules");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const addRule = async () => {
    setError(null);
    try {
      const rule = automationRuleSchema.parse({
        id: "",
        name,
        enabled: true,
        condition,
        condition_value: Number(conditionValue),
        action,
        cooldown_minutes: 30,
      });
      const data = automationRulesResponseSchema.parse(
        await apiClient.post("/controls/rules", rule),
      );
      setRules(data.rules);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add rule");
    }
  };

  const removeRule = async (id: string) => {
    try {
      const data = automationRulesResponseSchema.parse(
        await apiClient.delete(`/controls/rules/${id}`),
      );
      setRules(data.rules);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete rule");
    }
  };

  return (
    <section className="solar-card space-y-4">
      <div>
        <h3 className="solar-section-title">Automation rules</h3>
        <p className="text-sm text-[var(--muted)]">
          Simple if/then rules evaluated on each metric sample.
        </p>
      </div>
      {loading ? <p className="text-sm text-[var(--muted)]">Loading…</p> : null}
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
      <ul className="space-y-2">
        {rules.map((rule) => (
          <li
            key={rule.id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
          >
            <span>
              <strong>{rule.name}</strong> — {rule.condition} {rule.condition_value} → {rule.action}
            </span>
            <button
              type="button"
              className="solar-btn-ghost text-xs"
              disabled={disabled}
              onClick={() => void removeRule(rule.id)}
            >
              Delete
            </button>
          </li>
        ))}
        {!loading && rules.length === 0 ? (
          <li className="text-sm text-[var(--muted)]">No rules yet.</li>
        ) : null}
      </ul>
      <div className="grid gap-2 sm:grid-cols-2">
        <input className="solar-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Rule name" />
        <select className="solar-input" value={condition} onChange={(e) => setCondition(e.target.value)}>
          <option value="soc_below">SOC below</option>
          <option value="soc_above">SOC above</option>
          <option value="car_charging">Car charging</option>
          <option value="dispatch_active">Dispatch active</option>
          <option value="export_rate_above">Export rate above</option>
        </select>
        <input
          className="solar-input"
          value={conditionValue}
          onChange={(e) => setConditionValue(e.target.value)}
          placeholder="Threshold"
        />
        <select className="solar-input" value={action} onChange={(e) => setAction(e.target.value)}>
          <option value="raise_alert">Raise alert</option>
          <option value="force_battery_charge">Force charge</option>
          <option value="force_battery_stop">Force stop</option>
          <option value="set_auto_schedule">Toggle auto-schedule</option>
        </select>
      </div>
      <button type="button" className="solar-btn-primary" disabled={disabled} onClick={() => void addRule()}>
        Add rule
      </button>
    </section>
  );
}
