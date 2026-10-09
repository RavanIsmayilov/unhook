"use client";

import { useState } from "react";
import { BarList, ChartCard, DailyChart } from "@/components/charts";
import { BlocklistTable, CampaignCard } from "@/components/lists";
import { Card, Chip, Notice, SectionTitle, StatTile, VerdictBadge } from "@/components/ui";
import { downloadBlocklistCsv, getBlocklist, getCampaigns, getFeedback, getRecent, getStats } from "@/lib/api";
import { SOURCE_AZ, timeAgo } from "@/lib/format";
import type { FeedbackRow, ReportRow } from "@/lib/types";
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
          <p className="text-ink2">
            Bank və telekomlar üçün: brendinizi təqlid edən kampaniyalar real vaxtda.{" "}
            <a href="/partner" className="font-medium text-s1 underline underline-offset-2">Tərəfdaş girişi</a>
            {" · "}
            <a href="/integration" className="font-medium text-s1 underline underline-offset-2">API sənədi</a>
          </p>
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
            <button
              type="button"
              onClick={() => downloadBlocklistCsv(brand || undefined).catch(() => {})}
              className="rounded-lg border border-line bg-surface px-3 py-1.5 text-sm font-medium hover:bg-page"
            >
              ⬇ CSV yüklə
            </button>
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
