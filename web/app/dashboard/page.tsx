"use client";

import { useState } from "react";
import { BarList, ChartCard, DailyChart } from "@/components/charts";
import { Card, Chip, Notice, SectionTitle, StatTile, VerdictBadge } from "@/components/ui";
import { blocklistCsvUrl, getBlocklist, getCampaigns, getFeedback, getRecent, getStats } from "@/lib/api";
import { SOURCE_AZ, timeAgo } from "@/lib/format";
import type { BlocklistRow, Campaign, FeedbackRow, ReportRow } from "@/lib/types";
import { useNow, usePolling } from "@/lib/usePolling";

const REFRESH_MS = 5000;

export default function Dashboard() {
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

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Fırıldaq paneli</h1>
          <p className="text-ink2">Bank və telekomlar üçün: brendinizi təqlid edən kampaniyalar real vaxtda.</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-ink2" aria-live="off">
          <span className={`inline-block h-2.5 w-2.5 rounded-full ${offline ? "bg-warn" : "bg-good"}`} aria-hidden />
          {offline ? "Əlaqə yoxdur" : "Canlı"}
          {updatedAt > 0 && <span>· yeniləndi {timeAgo(new Date(updatedAt).toISOString(), now)}</span>}
        </div>
      </div>

      {offline && (
        <Notice tone="warn">
          Serverlə əlaqə kəsildi{s ? ", son məlumat göstərilir" : ""}. Backend işləyirmi və NEXT_PUBLIC_API_URL düzgündürmü?
        </Notice>
      )}

      {!s && !offline && <p className="text-ink2">Yüklənir...</p>}

      {s && (
        <>
          <section aria-label="Əsas göstəricilər" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile label="Cəmi yoxlama" value={s.total_reports.toLocaleString("az")} hint={`son 24 saat: ${s.reports_last_24h}`} />
            <StatTile label="Fırıldaq aşkarlandı" value={s.by_verdict.scam.toLocaleString("az")} hint={`şübhəli: ${s.by_verdict.suspicious}`} />
            <StatTile label="Kampaniyalar" value={s.campaigns_total} hint="oxşar mesajlar qrupu" />
            <StatTile label="Aktiv kampaniya" value={s.campaigns_active_24h} hint="son 24 saatda yeni hesabat" />
          </section>

          {s.total_reports === 0 && (
            <Notice>Hələ heç bir yoxlama yoxdur. Ana səhifədə mesaj yoxlayın, Telegram botuna yazın və ya demo data üçün <code>python seed_demo.py</code> işlədin.</Notice>
          )}

          <section aria-label="Statistika" className="grid gap-4 lg:grid-cols-2">
            <ChartCard
              title="Son 7 gün"
              note="Gündəlik yoxlamalar"
              table={{ head: ["Gün", "Cəmi", "Fırıldaq"], rows: s.daily.map((d) => [d.date, d.total, d.scam]) }}
            >
              <DailyChart data={s.daily} />
            </ChartCard>
            <ChartCard
              title="Fırıldaq üsulları"
              note="Aşkarlanan mesajlar üsula görə"
              table={{ head: ["Üsul", "Say"], rows: s.by_scheme.map((x) => [x.scheme_az, x.count]) }}
            >
              {s.by_scheme.length ? (
                <BarList rows={s.by_scheme.map((x) => ({ label: x.scheme_az, value: x.count, display: String(x.count) }))} />
              ) : (
                <p className="text-sm text-ink2">Hələ məlumat yoxdur.</p>
              )}
            </ChartCard>
            <ChartCard
              title="Hədəf alınan brendlər"
              note="Saxta linklərdə təqlid edilən adlar"
              table={{ head: ["Brend", "Say"], rows: s.top_brands.map((x) => [x.brand, x.count]) }}
            >
              {s.top_brands.length ? (
                <BarList rows={s.top_brands.map((x) => ({ label: x.brand, value: x.count, display: String(x.count) }))} />
              ) : (
                <p className="text-sm text-ink2">Hələ brend təqlidi aşkarlanmayıb.</p>
              )}
            </ChartCard>
            <ChartCard
              title="Ən çox rast gəlinən saxta domenlər"
              note="Bloklama üçün siyahı"
              table={{ head: ["Domen", "Say"], rows: s.top_domains.map((x) => [x.domain, x.count]) }}
            >
              {s.top_domains.length ? (
                <BarList rows={s.top_domains.map((x) => ({ label: x.domain, value: x.count, display: String(x.count) }))} />
              ) : (
                <p className="text-sm text-ink2">Hələ saxta domen yoxdur.</p>
              )}
            </ChartCard>
          </section>
        </>
      )}

      <section aria-label="Kampaniyalar">
        <SectionTitle
          hint="Eyni mətn və ya eyni saxta domen ətrafında birləşən hesabatlar"
          right={
            <label className="flex items-center gap-2 text-sm text-ink2">
              Brend
              <select
                value={brand}
                onChange={(e) => setBrand(e.target.value)}
                className="rounded-lg border border-line bg-surface px-2.5 py-1.5 text-sm text-ink"
              >
                <option value="">Hamısı</option>
                {brands.map((b) => <option key={b} value={b}>{b}</option>)}
              </select>
            </label>
          }
        >
          Kampaniyalar
        </SectionTitle>
        <div className={`space-y-3 transition-opacity ${campaigns.refreshing ? "opacity-80" : ""}`}>
          {campaigns.data?.length === 0 && (
            <Card><p className="text-sm text-ink2">{brand ? `${brand} üçün kampaniya tapılmadı.` : "Hələ kampaniya yoxdur. Kampaniya üçün ən azı 2 oxşar hesabat lazımdır."}</p></Card>
          )}
          {campaigns.data?.map((c) => <CampaignCard key={c.id} campaign={c} now={now} />)}
        </div>
      </section>

      <section aria-label="Blok siyahısı">
        <SectionTitle
          hint="Fırıldaq hesabatlarında görünən saxta domenlər. Bank və telekomlar öz bloklama sisteminə əlavə edə bilər."
          right={
            <a
              href={blocklistCsvUrl(brand || undefined)}
              className="rounded-lg border border-line bg-surface px-3 py-1.5 text-sm font-medium hover:bg-page"
              download
            >
              ⬇ CSV yüklə
            </a>
          }
        >
          Blok siyahısı{brand ? `: ${brand}` : ""}
        </SectionTitle>
        <Card className="!p-0">
          <BlocklistTable rows={blocklist.data ?? []} now={now} />
        </Card>
        <p className="mt-2 text-xs text-ink2">Siyahı avtomatik yaradılır və insan tərəfindən yoxlanmayıb. Bloklamazdan əvvəl yoxlayın.</p>
      </section>

      <section aria-label="Geri bildirimlər">
        <SectionTitle hint="İnsanlar “bu cavab səhvdir” dedikdə mesaj test nümunəsi kimi saxlanılır">Geri bildirimlər</SectionTitle>
        <div className="mb-3 grid grid-cols-3 gap-3">
          <StatTile label="Cəmi" value={s?.feedback.total ?? 0} />
          <StatTile label="Düzgün" value={s?.feedback.agree ?? 0} />
          <StatTile label="Səhv" value={s?.feedback.disagree ?? 0} />
        </div>
        <Card className="!p-0">
          <FeedbackList rows={feedback.data ?? []} now={now} />
        </Card>
      </section>

      <section aria-label="Son yoxlamalar">
        <SectionTitle hint="Şəxsi məlumatlar silinmiş formada">Son yoxlamalar</SectionTitle>
        <Card className="!p-0">
          <ul className="divide-y divide-grid">
            {recent.data?.length === 0 && <li className="p-4 text-sm text-ink2">Hələ yoxlama yoxdur.</li>}
            {recent.data?.map((r) => <RecentRow key={r.id} report={r} now={now} />)}
          </ul>
        </Card>
      </section>
    </div>
  );
}

function CampaignCard({ campaign: c, now }: { campaign: Campaign; now: number }) {
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

function RecentRow({ report: r, now }: { report: ReportRow; now: number }) {
  return (
    <li className="px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <VerdictBadge verdict={r.verdict} />
        {r.scheme !== "none" && <span className="text-sm font-medium">{r.scheme_az}</span>}
        <span className="ml-auto text-xs text-ink2">{SOURCE_AZ[r.source] ?? r.source} · {timeAgo(r.created_at, now)}</span>
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

const STATUS_AZ: Record<BlocklistRow["status"], string> = {
  lookalike: "brend təqlidi",
  suspicious: "şübhəli domen",
  unknown: "yoxlanmayıb",
  shortener: "qısa link",
  official: "rəsmi",
};

function BlocklistTable({ rows, now }: { rows: BlocklistRow[]; now: number }) {
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

const LABEL_AZ = { scam: "fırıldaq", suspicious: "şübhəli", safe: "təhlükəsiz" } as const;

function FeedbackList({ rows, now }: { rows: FeedbackRow[]; now: number }) {
  if (rows.length === 0) return <p className="p-4 text-sm text-ink2">Hələ “səhvdir” bildirimi yoxdur.</p>;
  return (
    <ul className="divide-y divide-grid">
      {rows.map((r) => (
        <li key={r.id} className="px-4 py-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span>Sistem: <b>{LABEL_AZ[r.model_verdict]}</b></span>
            <span aria-hidden>→</span>
            <span>İnsan: <b>{r.suggested ? LABEL_AZ[r.suggested] : "?"}</b></span>
            <span className="ml-auto text-xs text-ink2">{timeAgo(r.created_at, now)}</span>
          </div>
          <p className="mt-1 line-clamp-2 text-sm text-ink2">{r.text_redacted}</p>
        </li>
      ))}
    </ul>
  );
}
