"use client";

import { useState } from "react";

type UkDateInputProps = {
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  className?: string;
  id?: string;
  "aria-label"?: string;
};

/** Convert ISO yyyy-mm-dd → dd/mm/yyyy for display. */
export function isoToUkDate(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso.trim());
  if (!match) return "";
  return `${match[3]}/${match[2]}/${match[1]}`;
}

/** Parse dd/mm/yyyy (or yyyy-mm-dd) → ISO yyyy-mm-dd, or null if invalid. */
export function ukDateToIso(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const isoMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trimmed);
  if (isoMatch) {
    const [, y, m, d] = isoMatch;
    if (isValidYmd(+y, +m, +d)) return `${y}-${m}-${d}`;
    return null;
  }
  const ukMatch = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(trimmed);
  if (!ukMatch) return null;
  const day = Number(ukMatch[1]);
  const month = Number(ukMatch[2]);
  const year = Number(ukMatch[3]);
  if (!isValidYmd(year, month, day)) return null;
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function isValidYmd(year: number, month: number, day: number): boolean {
  if (month < 1 || month > 12 || day < 1 || day > 31) return false;
  const date = new Date(Date.UTC(year, month - 1, day));
  return (
    date.getUTCFullYear() === year
    && date.getUTCMonth() === month - 1
    && date.getUTCDate() === day
  );
}

/**
 * UK date field: displays and accepts dd/mm/yyyy.
 * Value passed to onChange remains ISO yyyy-mm-dd for the API.
 * Avoids native type="date" which follows OS locale (often US mm/dd/yyyy).
 */
export function UkDateInput({
  value,
  onChange,
  required,
  className = "solar-input",
  id,
  "aria-label": ariaLabel = "Date (dd/mm/yyyy)",
}: UkDateInputProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const display = editing ? draft : value ? isoToUkDate(value) : "";

  return (
    <label className="block space-y-1 text-sm">
      <span className="text-[var(--muted)]">Date (dd/mm/yyyy)</span>
      <input
        id={id}
        className={className}
        type="text"
        inputMode="numeric"
        placeholder="dd/mm/yyyy"
        lang="en-GB"
        autoComplete="off"
        value={display}
        required={required}
        aria-label={ariaLabel}
        onFocus={() => {
          setDraft(value ? isoToUkDate(value) : "");
          setEditing(true);
        }}
        onChange={(event) => {
          const next = event.target.value;
          setDraft(next);
          if (!next.trim()) {
            onChange("");
            return;
          }
          const iso = ukDateToIso(next);
          if (iso) onChange(iso);
        }}
        onBlur={() => {
          if (!draft.trim()) {
            onChange("");
          } else {
            const iso = ukDateToIso(draft);
            if (iso) onChange(iso);
          }
          setEditing(false);
        }}
      />
    </label>
  );
}
