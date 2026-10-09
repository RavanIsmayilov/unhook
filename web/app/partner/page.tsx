"use client";

import { useEffect, useState } from "react";
import { BlocklistTable, CampaignCard } from "@/components/lists";
import { Card, Notice, SectionTitle, StatTile } from "@/components/ui";
import { ApiError, downloadPartnerCsv, partnerBlocklist, partnerCampaigns, partnerMe, partnerSummary } from "@/lib/api";
import type { PartnerInfo } from "@/lib/types";
import { useNow, usePolling } from "@/lib/usePolling";

const STORAGE_KEY = "unhook-partner-key";

export default function PartnerPage() {
  const [key, setKey] = useState<string | null>(null);
  const [info, setInfo] = useState<PartnerInfo | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function login(candidate: string) {
    setBusy(true);
    setError(null);
    try {
      setInfo(await partnerMe(candidate));
      setKey(candidate);
      try { sessionStorage.setItem(STORAGE_KEY, candidate); } catch {}
    } catch (e) {
      setKey(null);
      setError(e instanceof ApiError && e.status === 401 ? "Açar yanlışdır və ya ləğv edilib." : "Serverə qoşulmaq mümkün olmadı.");
      try { sessionStorage.removeItem(STORAGE_KEY); } catch {}
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      if (saved) login(saved);
    } catch {}
  }, []);

  function logout() {
    setKey(null);
    setInfo(null);
    setDraft("");
    try { sessionStorage.removeItem(STORAGE_KEY); } catch {}
  }

  if (!key || !info) {
    return (
      <div className="mx-auto max-w-md space-y-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Tərəfdaş paneli</h1>
          <p className="mt-1 text-ink2">Bank və telekomlar üçün: yalnız öz brendinizi təqlid edən kampaniyaları görürsünüz.</p>
        </div>
        <form onSubmit={(e) => { e.preventDefault(); if (draft.trim()) login(draft.trim()); }} className="space-y-3 rounded-2xl border border-line bg-surface p-5">
          <label htmlFor="apikey" className="block text-sm font-semibold">API açarı</label>
          <input
            id="apikey"
            type="password"
            autoComplete="off"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="unhook_..."
            className="w-full rounded-xl border border-line bg-page px-3 py-2.5 font-mono text-base"
          />
          {error && <Notice tone="warn">{error}</Notice>}
          <button type="submit" disabled={busy || !draft.trim()} className="min-h-12 w-full rounded-xl bg-s1 px-4 py-3 font-semibold text-white disabled:opacity-40">
            {busy ? "Yoxlayıram..." : "Daxil ol"}
          </button>
        </form>
        <p className="text-sm text-ink2">
          Açarınız yoxdur? <a href="/integration" className="font-medium text-s1 underline underline-offset-2">İnteqrasiya sənədinə</a> baxın.
        </p>
      </div>
    );
  }

  return <Panel apiKey={key} info={info} onLogout={logout} />;
}

function Panel({ apiKey, info, onLogout }: { apiKey: string; info: PartnerInfo; onLogout: () => void }) {
  const now = useNow();
  const summary = usePolling(() => partnerSummary(apiKey), 10_000);
  const campaigns = usePolling(() => partnerCampaigns(apiKey), 10_000);
  const blocklist = usePolling(() => partnerBlocklist(apiKey), 10_000);
  const [csvError, setCsvError] = useState(false);
  const s = summary.data;
  const offline = summary.error || campaigns.error || blocklist.error;
  const scope = info.brand ?? "bütün brendlər";

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{info.name}</h1>
          <p className="text-ink2">Göstərilən: <b className="text-ink">{scope}</b>. Başqa brendlərin məlumatı bu paneldə görünmür.</p>
        </div>
        <button type="button" onClick={onLogout} className="rounded-lg border border-line bg-surface px-3 py-1.5 text-sm hover:bg-page">Çıxış</button>
      </div>

      {offline && <Notice tone="warn">Serverlə əlaqə kəsildi{s ? ", son məlumat göstərilir" : ""}.</Notice>}

      <section aria-label="Göstəricilər" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Fırıldaq hesabatı" value={s?.reports_total ?? "…"} hint={`son 24 saat: ${s?.reports_last_24h ?? "…"}`} />
        <StatTile label="Kampaniyalar" value={s?.campaigns ?? "…"} hint="oxşar mesajlar qrupu" />
        <StatTile label="Aktiv (24 saat)" value={s?.campaigns_active_24h ?? "…"} hint="yeni hesabat gələn" />
        <StatTile label="Saxta domenlər" value={s?.blocklist_domains ?? "…"} hint="bloklama üçün" />
      </section>

      {info.webhook && <Notice>🔔 Webhook aktivdir: brendinizi təqlid edən yeni fırıldaq aşkarlananda sizin ünvana avtomatik bildiriş göndərilir.</Notice>}

      <section aria-label="Kampaniyalar" className="space-y-3">
        <SectionTitle hint="Eyni mətn və ya eyni saxta domen ətrafında birləşən hesabatlar">Kampaniyalar</SectionTitle>
        {campaigns.data?.length === 0 && <Card><p className="text-sm text-ink2">Brendiniz üçün hələ kampaniya yoxdur.</p></Card>}
        {campaigns.data?.map((c) => <CampaignCard key={c.id} campaign={c} now={now} />)}
      </section>

      <section aria-label="Blok siyahısı">
        <SectionTitle
          hint="Brendinizi təqlid edən saxta domenlər"
          right={
            <button
              type="button"
              onClick={() => downloadPartnerCsv(apiKey).then(() => setCsvError(false)).catch(() => setCsvError(true))}
              className="rounded-lg border border-line bg-surface px-3 py-1.5 text-sm font-medium hover:bg-page"
            >
              ⬇ CSV yüklə
            </button>
          }
        >
          Blok siyahısı
        </SectionTitle>
        {csvError && <Notice tone="warn">CSV yüklənmədi.</Notice>}
        <Card className="!p-0"><BlocklistTable rows={blocklist.data ?? []} now={now} /></Card>
        <p className="mt-2 text-xs text-ink2">Siyahı avtomatik yaradılır və insan tərəfindən yoxlanmayıb. Bloklamazdan əvvəl yoxlayın.</p>
      </section>
    </div>
  );
}
