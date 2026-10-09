"use client";

import { useState } from "react";
import { BarList, ChartCard, DailyChart } from "@/components/charts";
import { BlocklistTable, CampaignCard } from "@/components/lists";
import { Card, Chip, Notice, SectionTitle, StatTile, VerdictBadge } from "@/components/ui";
import { downloadBlocklistCsv, getBlocklist, getCampaigns, getFeedback, getRecent, getStats } from "@/lib/api";
import { sourceLabel, timeAgo } from "@/lib/format";
import { LOCALES, schemeLabel, useLang } from "@/lib/i18n";
import type { FeedbackRow, ReportRow } from "@/lib/types";
import { useNow, usePolling } from "@/lib/usePolling";

const REFRESH_MS = 5000;

export default function Dashboard() {
  const { t, lang } = useLang();
  const [brand, setBrand] = useState("");
  const now = useNow();
  const stats = usePolling(getStats, REFRESH_MS);
  const campaigns = usePolling(() => getCampaigns(brand || undefined), REFRESH_MS, [brand]);
  const recent = usePolling(() => getRecent(20), REFRESH_MS);
  const blocklist = usePolling(() => getBlocklist(brand || undefined), REFRESH_MS, [brand]);
  const feedback = usePolling(getFeedback, REFRESH_MS);

  const s = stats.data;
  const offline = stats.error || campaigns.error || recent.error || blocklist.error || feedback.error;
  const updatedAt = Math.max(stats.updatedAt ?? 0, campaigns.updatedAt ?? 0, recent.updatedAt ?? 0);
  const brands = s?.top_brands.map((b) => b.brand) ?? [];
  const num = (n: number) => n.toLocaleString(LOCALES[lang]);

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{t("dash.title")}</h1>
          <p className="text-ink2">
            {t("dash.sub")}{" "}
            <a href="/partner" className="font-medium text-s1 underline underline-offset-2">{t("dash.partner")}</a>
            {" · "}
            <a href="/integration" className="font-medium text-s1 underline underline-offset-2">{t("dash.api")}</a>
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-ink2" aria-live="off">
          <span className={`inline-block h-2.5 w-2.5 rounded-full ${offline ? "bg-warn" : "bg-good"}`} aria-hidden />
          {offline ? t("dash.offline") : t("dash.live")}
          {updatedAt > 0 && <span>{t("dash.updated", { when: timeAgo(new Date(updatedAt).toISOString(), now, t) })}</span>}
        </div>
      </div>

      {offline && <Notice tone="warn">{s ? t("dash.offline_stale") : t("dash.offline_notice")}</Notice>}

      {!s && !offline && <p className="text-ink2">{t("common.loading")}</p>}

      {s && (
        <>
          <section aria-label={t("dash.kpi.aria")} className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile label={t("dash.kpi.total")} value={num(s.total_reports)} hint={t("dash.kpi.total_hint", { n: s.reports_last_24h })} />
            <StatTile label={t("dash.kpi.scam")} value={num(s.by_verdict.scam)} hint={t("dash.kpi.scam_hint", { n: s.by_verdict.suspicious })} />
            <StatTile label={t("dash.kpi.campaigns")} value={s.campaigns_total} hint={t("dash.kpi.campaigns_hint")} />
            <StatTile label={t("dash.kpi.active")} value={s.campaigns_active_24h} hint={t("dash.kpi.active_hint")} />
          </section>

          {s.total_reports === 0 && <Notice>{t("dash.empty")}</Notice>}

          <section aria-label={t("dash.stats_aria")} className="grid gap-4 lg:grid-cols-2">
            <ChartCard
              title={t("dash.week.title")}
              note={t("dash.week.note")}
              table={{ head: [t("dash.week.day"), t("dash.week.total"), t("chart.legend_scam")], rows: s.daily.map((d) => [d.date, d.total, d.scam]) }}
            >
              <DailyChart data={s.daily} />
            </ChartCard>
            <ChartCard
              title={t("dash.schemes.title")}
              note={t("dash.schemes.note")}
              table={{ head: [t("dash.schemes.th"), t("common.count")], rows: s.by_scheme.map((x) => [schemeLabel(t, x.scheme), x.count]) }}
            >
              {s.by_scheme.length ? (
                <BarList rows={s.by_scheme.map((x) => ({ label: schemeLabel(t, x.scheme), value: x.count, display: String(x.count) }))} />
              ) : (
                <p className="text-sm text-ink2">{t("common.no_data")}</p>
              )}
            </ChartCard>
            <ChartCard
              title={t("dash.brands.title")}
              note={t("dash.brands.note")}
              table={{ head: [t("common.brand"), t("common.count")], rows: s.top_brands.map((x) => [x.brand, x.count]) }}
            >
              {s.top_brands.length ? (
                <BarList rows={s.top_brands.map((x) => ({ label: x.brand, value: x.count, display: String(x.count) }))} />
              ) : (
                <p className="text-sm text-ink2">{t("dash.brands.empty")}</p>
              )}
            </ChartCard>
            <ChartCard
              title={t("dash.domains.title")}
              note={t("dash.domains.note")}
              table={{ head: [t("common.domain"), t("common.count")], rows: s.top_domains.map((x) => [x.domain, x.count]) }}
            >
              {s.top_domains.length ? (
                <BarList rows={s.top_domains.map((x) => ({ label: x.domain, value: x.count, display: String(x.count) }))} />
              ) : (
                <p className="text-sm text-ink2">{t("dash.domains.empty")}</p>
              )}
            </ChartCard>
          </section>
        </>
      )}

      <section aria-label={t("dash.camp.aria")}>
        <SectionTitle
          hint={t("dash.camp.hint")}
          right={
            <label className="flex items-center gap-2 text-sm text-ink2">
              {t("common.brand")}
              <select
                value={brand}
                onChange={(e) => setBrand(e.target.value)}
                className="rounded-lg border border-line bg-surface px-2.5 py-1.5 text-sm text-ink"
              >
                <option value="">{t("common.all")}</option>
                {brands.map((b) => <option key={b} value={b}>{b}</option>)}
              </select>
            </label>
          }
        >
          {t("dash.camp.title")}
        </SectionTitle>
        <div className={`space-y-3 transition-opacity ${campaigns.refreshing ? "opacity-80" : ""}`}>
          {campaigns.data?.length === 0 && (
            <Card><p className="text-sm text-ink2">{brand ? t("dash.camp.empty_brand", { brand }) : t("dash.camp.empty")}</p></Card>
          )}
          {campaigns.data?.map((c) => <CampaignCard key={c.id} campaign={c} now={now} />)}
        </div>
      </section>

      <section aria-label={t("dash.bl.aria")}>
        <SectionTitle
          hint={t("dash.bl.hint")}
          right={
            <button
              type="button"
              onClick={() => downloadBlocklistCsv(brand || undefined).catch(() => {})}
              className="rounded-lg border border-line bg-surface px-3 py-1.5 text-sm font-medium hover:bg-page"
            >
              {t("common.csv")}
            </button>
          }
        >
          {t("dash.bl.title")}{brand ? `: ${brand}` : ""}
        </SectionTitle>
        <Card className="!p-0">
          <BlocklistTable rows={blocklist.data ?? []} now={now} />
        </Card>
        <p className="mt-2 text-xs text-ink2">{t("dash.bl.note")}</p>
      </section>

      <section aria-label={t("dash.fb.aria")}>
        <SectionTitle hint={t("dash.fb.hint")}>{t("dash.fb.title")}</SectionTitle>
        <div className="mb-3 grid grid-cols-3 gap-3">
          <StatTile label={t("dash.fb.total")} value={s?.feedback.total ?? 0} />
          <StatTile label={t("dash.fb.agree")} value={s?.feedback.agree ?? 0} />
          <StatTile label={t("dash.fb.disagree")} value={s?.feedback.disagree ?? 0} />
        </div>
        <Card className="!p-0">
          <FeedbackList rows={feedback.data ?? []} now={now} />
        </Card>
      </section>

      <section aria-label={t("dash.recent.aria")}>
        <SectionTitle hint={t("dash.recent.hint")}>{t("dash.recent.title")}</SectionTitle>
        <Card className="!p-0">
          <ul className="divide-y divide-grid">
            {recent.data?.length === 0 && <li className="p-4 text-sm text-ink2">{t("dash.recent.empty")}</li>}
            {recent.data?.map((r) => <RecentRow key={r.id} report={r} now={now} />)}
          </ul>
        </Card>
      </section>
    </div>
  );
}

function RecentRow({ report: r, now }: { report: ReportRow; now: number }) {
  const { t } = useLang();
  return (
    <li className="px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <VerdictBadge verdict={r.verdict} />
        {r.scheme !== "none" && <span className="text-sm font-medium">{schemeLabel(t, r.scheme)}</span>}
        <span className="ml-auto text-xs text-ink2">{sourceLabel(t, r.source)} · {timeAgo(r.created_at, now, t)}</span>
      </div>
      <p className="mt-1 line-clamp-2 text-sm text-ink2">{r.text_redacted}</p>
      {(r.brands.length > 0 || r.domains.length > 0) && (
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {r.brands.map((b) => <Chip key={b}>🎯 {b}</Chip>)}
          {r.domains.slice(0, 2).map((d) => <Chip key={d} mono>{d}</Chip>)}
        </div>
      )}
    </li>
  );
}

function FeedbackList({ rows, now }: { rows: FeedbackRow[]; now: number }) {
  const { t } = useLang();
  if (rows.length === 0) return <p className="p-4 text-sm text-ink2">{t("dash.fb.empty")}</p>;
  return (
    <ul className="divide-y divide-grid">
      {rows.map((r) => (
        <li key={r.id} className="px-4 py-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span>{t("dash.fb.system")} <b>{t(`verdict.${r.model_verdict}.word`)}</b></span>
            <span aria-hidden>→</span>
            <span>{t("dash.fb.human")} <b>{r.suggested ? t(`verdict.${r.suggested}.word`) : "?"}</b></span>
            <span className="ml-auto text-xs text-ink2">{timeAgo(r.created_at, now, t)}</span>
          </div>
          <p className="mt-1 line-clamp-2 text-sm text-ink2">{r.text_redacted}</p>
        </li>
      ))}
    </ul>
  );
}
