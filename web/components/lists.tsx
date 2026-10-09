import type { BlocklistRow, Campaign } from "@/lib/types";
import { timeAgo } from "@/lib/format";
import { Card, Chip } from "./ui";

export function CampaignCard({ campaign: c, now }: { campaign: Campaign; now: number }) {
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="min-w-0 text-base font-semibold">{c.name}</h3>
        <div className="flex items-center gap-2 text-sm">
          <span className="rounded-full bg-s1 px-2.5 py-0.5 text-xs font-semibold text-white tabular-nums">{c.count} hesabat</span>
          {c.reports_last_24h > 0 && <span className="text-xs text-ink2">son 24 saat: {c.reports_last_24h}</span>}
        </div>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {c.brands.map((b) => <Chip key={b}>🎯 {b}</Chip>)}
        {c.domains.map((d) => <Chip key={d} mono>{d}</Chip>)}
      </div>
      <blockquote className="mt-3 line-clamp-3 border-l-2 border-axis pl-3 text-sm text-ink2">{c.example}</blockquote>
      <p className="mt-2 text-xs text-ink2">
        Son hesabat: {timeAgo(c.last_seen, now)} · ilk hesabat: {timeAgo(c.first_seen, now)}
        {" · "}
        {(["scam", "suspicious"] as const).filter((v) => c.verdicts[v]).map((v) => `${v === "scam" ? "fırıldaq" : "şübhəli"} ${c.verdicts[v]}`).join(", ")}
      </p>
    </Card>
  );
}


const STATUS_AZ: Record<BlocklistRow["status"], string> = {
  lookalike: "brend təqlidi",
  suspicious: "şübhəli domen",
  unknown: "yoxlanmayıb",
  shortener: "qısa link",
  official: "rəsmi",
};

export function BlocklistTable({ rows, now }: { rows: BlocklistRow[]; now: number }) {
  if (rows.length === 0) return <p className="p-4 text-sm text-ink2">Hələ saxta domen yoxdur.</p>;
  return (
    <div className="max-h-96 overflow-auto">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 bg-surface text-ink2">
          <tr className="border-b border-line">
            <th className="px-4 py-2 font-medium">Domen</th>
            <th className="px-2 py-2 font-medium">Hesabat</th>
            <th className="hidden px-2 py-2 font-medium sm:table-cell">Brend</th>
            <th className="hidden px-2 py-2 font-medium sm:table-cell">Növ</th>
            <th className="px-4 py-2 font-medium">Son</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.domain} className="border-b border-grid last:border-0">
              <td className="px-4 py-2 font-mono text-[13px]">{r.domain}</td>
              <td className="px-2 py-2 tabular-nums">{r.reports}</td>
              <td className="hidden px-2 py-2 sm:table-cell">{r.brands.join(", ") || "—"}</td>
              <td className="hidden px-2 py-2 sm:table-cell">{STATUS_AZ[r.status]}</td>
              <td className="px-4 py-2 text-ink2">{timeAgo(r.last_seen, now)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

