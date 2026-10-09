"use client";

import { timeAgo } from "@/lib/format";
import { schemeLabel, useLang, type TFunction } from "@/lib/i18n";
import type { MessageKey } from "@/lib/messages/az";
import type { BlocklistRow, Campaign } from "@/lib/types";
import { Card, Chip } from "./ui";

/** Named from the scheme code, the brand and the domain, so it reads in the visitor's language. */
export function campaignName(t: TFunction, c: Campaign): string {
  return [schemeLabel(t, c.scheme), c.brands[0], c.domains[0]].filter(Boolean).join(" · ");
}

export function CampaignCard({ campaign: c, now }: { campaign: Campaign; now: number }) {
  const { t } = useLang();
  const verdicts = (["scam", "suspicious"] as const)
    .filter((v) => c.verdicts[v])
    .map((v) => `${t(`verdict.${v}.word`)} ${c.verdicts[v]}`)
    .join(", ");
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="min-w-0 text-base font-semibold">{campaignName(t, c)}</h3>
        <div className="flex items-center gap-2 text-sm">
          <span className="rounded-full bg-s1 px-2.5 py-0.5 text-xs font-semibold text-white tabular-nums">{t("camp.reports", { n: c.count })}</span>
          {c.reports_last_24h > 0 && <span className="text-xs text-ink2">{t("camp.last24", { n: c.reports_last_24h })}</span>}
        </div>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {c.brands.map((b) => <Chip key={b}>🎯 {b}</Chip>)}
        {c.domains.map((d) => <Chip key={d} mono>{d}</Chip>)}
      </div>
      <blockquote className="mt-3 line-clamp-3 border-l-2 border-axis pl-3 text-sm text-ink2">{c.example}</blockquote>
      <p className="mt-2 text-xs text-ink2">
        {t("camp.times", { last: timeAgo(c.last_seen, now, t), first: timeAgo(c.first_seen, now, t) })}
        {verdicts ? ` · ${verdicts}` : ""}
      </p>
    </Card>
  );
}

export function BlocklistTable({ rows, now }: { rows: BlocklistRow[]; now: number }) {
  const { t } = useLang();
  if (rows.length === 0) return <p className="p-4 text-sm text-ink2">{t("bl.empty")}</p>;
  return (
    <div className="max-h-96 overflow-auto">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 bg-surface text-ink2">
          <tr className="border-b border-line">
            <th className="px-4 py-2 font-medium">{t("common.domain")}</th>
            <th className="px-2 py-2 font-medium">{t("bl.reports")}</th>
            <th className="hidden px-2 py-2 font-medium sm:table-cell">{t("common.brand")}</th>
            <th className="hidden px-2 py-2 font-medium sm:table-cell">{t("bl.kind")}</th>
            <th className="px-4 py-2 font-medium">{t("bl.last")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.domain} className="border-b border-grid last:border-0">
              <td className="px-4 py-2 font-mono text-[13px]">{r.domain}</td>
              <td className="px-2 py-2 tabular-nums">{r.reports}</td>
              <td className="hidden px-2 py-2 sm:table-cell">{r.brands.join(", ") || "—"}</td>
              <td className="hidden px-2 py-2 sm:table-cell">{t(`status.${r.status}` as MessageKey)}</td>
              <td className="px-4 py-2 text-ink2">{timeAgo(r.last_seen, now, t)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
