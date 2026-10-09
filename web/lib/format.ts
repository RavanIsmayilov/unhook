/** The API sends UTC timestamps without a "Z"; add it so the browser doesn't read them as local time. */
export function parseUtc(ts: string): Date {
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(ts) ? ts : `${ts}Z`);
}

export function timeAgo(ts: string, now: number = Date.now()): string {
  const s = Math.max(0, Math.round((now - parseUtc(ts).getTime()) / 1000));
  if (s < 10) return "indicə";
  if (s < 60) return `${s} san əvvəl`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m} dəq əvvəl`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} saat əvvəl`;
  return `${Math.round(h / 24)} gün əvvəl`;
}

export function pct(x: number | null | undefined, digits = 0): string {
  return x === null || x === undefined ? "—" : `${(x * 100).toFixed(digits)}%`;
}

export function shortDate(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${d}.${m}`;
}

export const SOURCE_AZ: Record<string, string> = { telegram: "Telegram", api: "Vebsayt", demo: "Demo", cli: "Terminal" };
