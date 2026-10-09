import type { MessageKey } from "./messages/az";
import type { TFunction } from "./i18n";

/** The API sends UTC timestamps without a "Z"; add it so the browser doesn't read them as local time. */
export function parseUtc(ts: string): Date {
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(ts) ? ts : `${ts}Z`);
}

export function timeAgo(ts: string, now: number, t: TFunction): string {
  const s = Math.max(0, Math.round((now - parseUtc(ts).getTime()) / 1000));
  if (s < 10) return t("time.now");
  if (s < 60) return t("time.sec", { n: s });
  const m = Math.round(s / 60);
  if (m < 60) return t("time.min", { n: m });
  const h = Math.round(m / 60);
  if (h < 24) return t("time.hour", { n: h });
  return t("time.day", { n: Math.round(h / 24) });
}

export function pct(x: number | null | undefined, digits = 0): string {
  return x === null || x === undefined ? "—" : `${(x * 100).toFixed(digits)}%`;
}

export function shortDate(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${d}.${m}`;
}

const SOURCES = new Set(["telegram", "api", "demo", "cli", "partner"]);
export const sourceLabel = (t: TFunction, source: string): string =>
  SOURCES.has(source) ? t(`source.${source}` as MessageKey) : source;
