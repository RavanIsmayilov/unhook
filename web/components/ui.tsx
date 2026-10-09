"use client";

import type { ReactNode } from "react";
import { useLang } from "@/lib/i18n";
import type { VerdictLabel } from "@/lib/types";

/** Colors and emoji per verdict; the words come from the dictionary (verdict.<name>.title / .label). */
export const VERDICT_STYLE: Record<VerdictLabel, { emoji: string; color: string; ink: string }> = {
  scam: { emoji: "🔴", color: "var(--crit)", ink: "text-crit-ink" },
  suspicious: { emoji: "🟡", color: "var(--warn)", ink: "text-warn-ink" },
  safe: { emoji: "🟢", color: "var(--good)", ink: "text-good-ink" },
};

export function tint(color: string, percent = 10): string {
  return `color-mix(in srgb, ${color} ${percent}%, var(--surface))`;
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-2xl border border-line bg-surface p-4 sm:p-5 ${className}`}>{children}</section>;
}

export function SectionTitle({ children, hint, right }: { children: ReactNode; hint?: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">{children}</h2>
        {hint && <p className="text-sm text-ink2">{hint}</p>}
      </div>
      {right}
    </div>
  );
}

export function Chip({ children, mono = false }: { children: ReactNode; mono?: boolean }) {
  return (
    <span className={`inline-flex items-center rounded-full border border-line px-2.5 py-0.5 text-xs text-ink2 ${mono ? "font-mono" : ""}`}>
      {children}
    </span>
  );
}

export function VerdictBadge({ verdict }: { verdict: VerdictLabel }) {
  const { t } = useLang();
  const m = VERDICT_STYLE[verdict];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"
      style={{ background: tint(m.color, 14), boxShadow: `inset 0 0 0 1px ${tint(m.color, 40)}` }}
    >
      <span aria-hidden>{m.emoji}</span>
      <span className={m.ink}>{t(`verdict.${verdict}.label`)}</span>
    </span>
  );
}

export function StatTile({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-2xl border border-line bg-surface p-4">
      <div className="text-sm text-ink2">{label}</div>
      <div className="mt-1 text-3xl font-semibold tracking-tight sm:text-4xl">{value}</div>
      {hint && <div className="mt-1 text-xs text-ink2">{hint}</div>}
    </div>
  );
}

export function Notice({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "warn" }) {
  const color = tone === "warn" ? "var(--warn)" : "var(--series-1)";
  return (
    <div role="status" className="rounded-xl px-4 py-3 text-sm" style={{ background: tint(color, 12), boxShadow: `inset 0 0 0 1px ${tint(color, 35)}` }}>
      {children}
    </div>
  );
}
