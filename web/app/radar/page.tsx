"use client";

import { useState } from "react";
import { Card, Chip, Notice, SectionTitle, StatTile } from "@/components/ui";
import { getCampaigns, getStats } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import { tipFor } from "@/lib/tips";
import type { Campaign } from "@/lib/types";
import { useNow, usePolling } from "@/lib/usePolling";

export default function Radar() {
  const now = useNow();
  const stats = usePolling(getStats, 15_000);
  const campaigns = usePolling(() => getCampaigns(), 15_000);
  const s = stats.data;
  const demo = s?.by_source.demo ?? 0;

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">📡 Fırıldaq radarı</h1>
        <p className="mt-1 text-ink2">
          İnsanların yoxladığı mesajlara görə hazırda yayılan fırıldaqlar. Tanıdığınız birinə göndərin, o da aldanmasın.
        </p>
      </div>

      {demo > 0 && <Notice>Məlumatın bir hissəsi <b>demo məqsədlidir</b> ({demo} hesabat). Real istifadədə yalnız həqiqi hesabatlar görünəcək.</Notice>}
      {(stats.error || campaigns.error) && <Notice tone="warn">Serverlə əlaqə kəsildi{s ? ", son məlumat göstərilir" : ""}.</Notice>}

      {s && (
        <section className="grid grid-cols-3 gap-3" aria-label="Göstəricilər">
          <StatTile label="Yoxlama" value={s.total_reports.toLocaleString("az")} />
          <StatTile label="Fırıldaq" value={s.by_verdict.scam.toLocaleString("az")} />
          <StatTile label="Aktiv kampaniya" value={s.campaigns_active_24h} hint="son 24 saat" />
        </section>
      )}

      {s && s.top_brands.length > 0 && (
        <section aria-label="Təqlid edilən brendlər">
          <SectionTitle hint="Fırıldaqçılar bu adlardan istifadə edir">Ən çox təqlid edilən brendlər</SectionTitle>
          <div className="flex flex-wrap gap-2">
            {s.top_brands.map((b) => <Chip key={b.brand}>🎯 {b.brand} · {b.count}</Chip>)}
          </div>
        </section>
      )}

      <section aria-label="Yayılan fırıldaqlar" className="space-y-3">
        <SectionTitle hint="Eyni mesajı bir neçə nəfər göndərib">Yayılan fırıldaqlar</SectionTitle>
        {campaigns.data?.length === 0 && <Card><p className="text-sm text-ink2">Hələ kampaniya yoxdur.</p></Card>}
        {campaigns.data?.slice(0, 8).map((c) => <RadarCard key={c.id} campaign={c} now={now} />)}
      </section>
    </div>
  );
}

function RadarCard({ campaign: c, now }: { campaign: Campaign; now: number }) {
  const [note, setNote] = useState("");
  const tip = tipFor(c.scheme);
  const url = typeof window !== "undefined" ? window.location.origin : "";
  const text = `⚠️ Fırıldaq xəbərdarlığı: ${c.scheme_az}${c.brands[0] ? ` (${c.brands[0]} adından)` : ""}${c.domains[0] ? `. Saxta sayt: ${c.domains[0]}` : ""}. Şübhəli mesajı Unhook ilə yoxlayın:`;

  async function share() {
    try {
      if (navigator.share) {
        await navigator.share({ title: "Unhook xəbərdarlığı", text, url });
        return;
      }
      await navigator.clipboard.writeText(`${text} ${url}`);
      setNote("Kopyalandı ✓");
      setTimeout(() => setNote(""), 2000);
    } catch {
      /* the person closed the share sheet */
    }
  }

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="font-semibold">{c.scheme_az}{c.brands[0] ? ` · ${c.brands[0]} adından` : ""}</h3>
        <span className="text-xs text-ink2">{c.count} nəfər yoxladı · {timeAgo(c.last_seen, now)}</span>
      </div>
      {c.domains.length > 0 && (
        <p className="mt-2 text-sm">
          Saxta sayt: {c.domains.map((d) => <code key={d} className="mr-1 rounded bg-page px-1.5 py-0.5 font-mono text-[13px]">{d}</code>)}
          <span className="text-ink2">(açmayın)</span>
        </p>
      )}
      <blockquote className="mt-3 line-clamp-3 border-l-2 border-axis pl-3 text-sm text-ink2">{c.example}</blockquote>
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer font-medium">🎓 Necə tanımaq olar?</summary>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-ink2 marker:text-muted">{tip.flags.map((f, i) => <li key={i}>{f}</li>)}</ul>
      </details>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button type="button" onClick={share} className="min-h-10 rounded-xl border border-line px-4 py-2 text-sm font-medium hover:bg-page">
          📤 Paylaş
        </button>
        <a
          href={`https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`}
          target="_blank"
          rel="noreferrer"
          className="min-h-10 rounded-xl border border-line px-4 py-2 text-sm font-medium hover:bg-page"
        >
          Telegram-da göndər
        </a>
        {note && <span className="text-sm text-ink2" role="status">{note}</span>}
      </div>
    </Card>
  );
}
