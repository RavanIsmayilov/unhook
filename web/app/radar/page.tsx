"use client";

import { useState } from "react";
import { campaignName } from "@/components/lists";
import { Card, Chip, Notice, SectionTitle, StatTile } from "@/components/ui";
import { getCampaigns, getStats } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import { LOCALES, schemeLabel, tipsFor, useLang } from "@/lib/i18n";
import type { Campaign } from "@/lib/types";
import { useNow, usePolling } from "@/lib/usePolling";

export default function Radar() {
  const { t, lang } = useLang();
  const now = useNow();
  const stats = usePolling(getStats, 15_000);
  const campaigns = usePolling(() => getCampaigns(), 15_000);
  const s = stats.data;
  const demo = s?.by_source.demo ?? 0;

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{t("radar.title")}</h1>
        <p className="mt-1 text-ink2">{t("radar.lead")}</p>
      </div>

      {demo > 0 && <Notice>{t("radar.demo", { n: demo })}</Notice>}
      {(stats.error || campaigns.error) && <Notice tone="warn">{s ? t("radar.offline_stale") : t("radar.offline")}</Notice>}

      {s && (
        <section className="grid grid-cols-3 gap-3" aria-label={t("radar.kpi.aria")}>
          <StatTile label={t("radar.kpi.checks")} value={s.total_reports.toLocaleString(LOCALES[lang])} />
          <StatTile label={t("radar.kpi.scams")} value={s.by_verdict.scam.toLocaleString(LOCALES[lang])} />
          <StatTile label={t("radar.kpi.active")} value={s.campaigns_active_24h} hint={t("radar.kpi.active_hint")} />
        </section>
      )}

      {s && s.top_brands.length > 0 && (
        <section aria-label={t("radar.brands.aria")}>
          <SectionTitle hint={t("radar.brands.hint")}>{t("radar.brands.title")}</SectionTitle>
          <div className="flex flex-wrap gap-2">
            {s.top_brands.map((b) => <Chip key={b.brand}>🎯 {b.brand} · {b.count}</Chip>)}
          </div>
        </section>
      )}

      <section aria-label={t("radar.spreading.aria")} className="space-y-3">
        <SectionTitle hint={t("radar.spreading.hint")}>{t("radar.spreading.title")}</SectionTitle>
        {campaigns.data?.length === 0 && <Card><p className="text-sm text-ink2">{t("radar.none")}</p></Card>}
        {campaigns.data?.slice(0, 8).map((c) => <RadarCard key={c.id} campaign={c} now={now} />)}
      </section>
    </div>
  );
}

function RadarCard({ campaign: c, now }: { campaign: Campaign; now: number }) {
  const { t } = useLang();
  const [note, setNote] = useState("");
  const tips = tipsFor(t, c.scheme);
  const url = typeof window !== "undefined" ? window.location.origin : "";
  const scheme = schemeLabel(t, c.scheme);
  const text = t("radar.share_text", {
    scheme,
    brand: c.brands[0] ? t("radar.share_brand", { brand: c.brands[0] }) : "",
    domain: c.domains[0] ? t("radar.share_domain", { domain: c.domains[0] }) : "",
  });

  async function share() {
    try {
      if (navigator.share) {
        await navigator.share({ title: t("radar.share_title"), text, url });
        return;
      }
      await navigator.clipboard.writeText(`${text} ${url}`);
      setNote(t("radar.card.copied"));
      setTimeout(() => setNote(""), 2000);
    } catch {
      /* the person closed the share sheet */
    }
  }

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="font-semibold">
          {c.brands[0] ? t("radar.card.title_brand", { scheme, brand: c.brands[0] }) : campaignName(t, { ...c, domains: [] })}
        </h3>
        <span className="text-xs text-ink2">{t("radar.card.checked", { n: c.count, when: timeAgo(c.last_seen, now, t) })}</span>
      </div>
      {c.domains.length > 0 && (
        <p className="mt-2 text-sm">
          {t("radar.card.site")} {c.domains.map((d) => <code key={d} className="mr-1 rounded bg-page px-1.5 py-0.5 font-mono text-[13px]">{d}</code>)}
          <span className="text-ink2">{t("radar.card.dont_open")}</span>
        </p>
      )}
      <blockquote className="mt-3 line-clamp-3 border-l-2 border-axis pl-3 text-sm text-ink2">{c.example}</blockquote>
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer font-medium">{t("radar.card.how")}</summary>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-ink2 marker:text-muted">{tips.flags.map((f, i) => <li key={i}>{f}</li>)}</ul>
      </details>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button type="button" onClick={share} className="min-h-10 rounded-xl border border-line px-4 py-2 text-sm font-medium hover:bg-page">
          {t("radar.card.share")}
        </button>
        <a
          href={`https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`}
          target="_blank"
          rel="noreferrer"
          className="min-h-10 rounded-xl border border-line px-4 py-2 text-sm font-medium hover:bg-page"
        >
          {t("radar.card.telegram")}
        </a>
        {note && <span className="text-sm text-ink2" role="status">{note}</span>}
      </div>
    </Card>
  );
}
