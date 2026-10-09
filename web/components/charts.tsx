"use client";

import { useState, type ReactNode } from "react";
import type { DailyPoint } from "@/lib/types";
import { shortDate } from "@/lib/format";
import { Card } from "./ui";

/** A chart card with a "table view" twin, so every value is reachable without color or hover. */
export function ChartCard({
  title,
  note,
  table,
  children,
}: {
  title: string;
  note?: string;
  table: { head: string[]; rows: (string | number)[][] };
  children: ReactNode;
}) {
  const [asTable, setAsTable] = useState(false);
  return (
    <Card>
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold">{title}</h3>
          {note && <p className="text-sm text-ink2">{note}</p>}
        </div>
        <button
          type="button"
          onClick={() => setAsTable((v) => !v)}
          aria-pressed={asTable}
          className="shrink-0 rounded-lg border border-line px-2.5 py-1 text-xs text-ink2 hover:bg-page"
        >
          {asTable ? "Qrafik" : "Cədvəl"}
        </button>
      </div>
      {asTable ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-ink2">
                {table.head.map((h) => (
                  <th key={h} className="py-1.5 pr-4 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, i) => (
                <tr key={i} className="border-b border-grid last:border-0">
                  {row.map((cell, j) => (
                    <td key={j} className="py-1.5 pr-4 tabular-nums">{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        children
      )}
    </Card>
  );
}

export interface BarRow {
  label: string;
  value: number;
  display: string;
  color?: string;
  sub?: string;
}

/** Horizontal bars from one baseline, value printed at the bar tip. `max` fixes the scale (e.g. 1 for percentages). */
export function BarList({ rows, max }: { rows: BarRow[]; max?: number }) {
  const top = max ?? Math.max(1, ...rows.map((r) => r.value));
  return (
    <ul className="space-y-3">
      {rows.map((r) => (
        <li key={r.label}>
          <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
            <span className="min-w-0 truncate">{r.label}</span>
            {r.sub && <span className="shrink-0 text-xs text-ink2">{r.sub}</span>}
          </div>
          <div className="flex items-center gap-2">
            <div
              className="h-3 rounded-r-[4px]"
              style={{
                width: `calc((100% - 3.5rem) * ${Math.min(1, r.value / top)})`,
                minWidth: r.value > 0 ? 3 : 0,
                background: r.color ?? "var(--series-1)",
              }}
              role="img"
              aria-label={`${r.label}: ${r.display}`}
            />
            <span className="text-sm font-semibold tabular-nums">{r.display}</span>
          </div>
        </li>
      ))}
    </ul>
  );
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <ul className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink2">
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: i.color }} aria-hidden />
          {i.label}
        </li>
      ))}
    </ul>
  );
}

/** Last 7 days as stacked columns: fırıldaq (accent) over the rest (gray). */
export function DailyChart({ data }: { data: DailyPoint[] }) {
  const [active, setActive] = useState<number | null>(null);
  const top = Math.max(1, ...data.map((d) => d.total));
  const niceTop = top <= 4 ? 4 : Math.ceil(top / 4) * 4;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(niceTop * f));
  const height = 168;

  return (
    <div>
      <Legend items={[{ label: "Fırıldaq", color: "var(--series-1)" }, { label: "Digər yoxlamalar", color: "var(--mark-gray)" }]} />
      <div className="flex gap-2">
        <div className="relative w-7 shrink-0 text-right text-[11px] text-muted tabular-nums" style={{ height }} aria-hidden>
          {ticks.map((t) => (
            <span key={t} className="absolute right-0" style={{ bottom: `${(t / niceTop) * 100}%`, transform: "translateY(50%)" }}>
              {t}
            </span>
          ))}
        </div>
        <div className="relative flex-1">
          <div className="absolute inset-x-0 top-0" style={{ height }} aria-hidden>
            {ticks.map((t) => (
              <div key={t} className="absolute inset-x-0 border-t" style={{ bottom: `${(t / niceTop) * 100}%`, borderColor: t === 0 ? "var(--axis)" : "var(--grid)" }} />
            ))}
          </div>
          <div className="relative flex items-end justify-between gap-1" style={{ height }}>
            {data.map((d, i) => {
              const rest = d.total - d.scam;
              return (
                <div
                  key={d.date}
                  className="relative flex h-full flex-1 cursor-default flex-col items-center justify-end"
                  tabIndex={0}
                  role="img"
                  aria-label={`${shortDate(d.date)}: cəmi ${d.total}, fırıldaq ${d.scam}`}
                  onPointerEnter={() => setActive(i)}
                  onPointerLeave={() => setActive(null)}
                  onFocus={() => setActive(i)}
                  onBlur={() => setActive(null)}
                >
                  <div className="flex w-full max-w-6 flex-col justify-end" style={{ height: `${(d.total / niceTop) * 100}%`, opacity: active === null || active === i ? 1 : 0.55 }}>
                    {rest > 0 && <div style={{ flex: rest, background: "var(--mark-gray)", borderRadius: "4px 4px 0 0", marginBottom: d.scam > 0 ? 2 : 0 }} />}
                    {d.scam > 0 && <div style={{ flex: d.scam, background: "var(--series-1)", borderRadius: rest > 0 ? 0 : "4px 4px 0 0" }} />}
                  </div>
                  {active === i && (
                    <div className="pointer-events-none absolute z-10 w-max -translate-x-1/2 rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-lg" style={{ left: "50%", bottom: `calc(${(d.total / niceTop) * 100}% + 4px)` }}>
                      <div className="text-ink2">{shortDate(d.date)}</div>
                      <div className="text-sm font-semibold tabular-nums">{d.total} yoxlama</div>
                      <div className="flex items-center gap-1.5 text-ink2"><span className="inline-block h-0.5 w-3" style={{ background: "var(--series-1)" }} />Fırıldaq: <b className="text-ink tabular-nums">{d.scam}</b></div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          <div className="mt-1.5 flex justify-between gap-1 text-[11px] text-muted tabular-nums">
            {data.map((d) => (
              <span key={d.date} className="flex-1 text-center">{shortDate(d.date)}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
