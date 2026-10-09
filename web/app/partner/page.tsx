"use client";

import { useEffect, useState } from "react";
import { BlocklistTable, CampaignCard } from "@/components/lists";
import { Card, Notice, SectionTitle, StatTile, Loading } from "@/components/ui";
import { ApiError, downloadPartnerCsv, partnerBlocklist, partnerCampaigns, partnerMe, partnerSummary } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import type { PartnerInfo } from "@/lib/types";
import { useNow, usePolling } from "@/lib/usePolling";

const STORAGE_KEY = "unhook-partner-key";

export default function PartnerPage() {
  const { t } = useLang();
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
      setError(e instanceof ApiError && e.status === 401 ? t("pt.bad_key") : t("pt.no_server"));
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
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{t("pt.title")}</h1>
          <p className="mt-1 text-ink2">{t("pt.lead")}</p>
        </div>
        <form onSubmit={(e) => { e.preventDefault(); if (draft.trim()) login(draft.trim()); }} className="space-y-3 rounded-2xl border border-line bg-surface p-5">
          <label htmlFor="apikey" className="block text-sm font-semibold">{t("pt.key")}</label>
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
            {busy ? t("pt.checking") : t("pt.login")}
          </button>
        </form>
        <p className="text-sm text-ink2">
          {t("pt.no_key")} <a href="/integration" className="font-medium text-s1 underline underline-offset-2">{t("pt.see_docs")}</a>{t("pt.see_docs_end")}
        </p>
      </div>
    );
  }

  return <Panel apiKey={key} info={info} onLogout={logout} />;
}

function Panel({ apiKey, info, onLogout }: { apiKey: string; info: PartnerInfo; onLogout: () => void }) {
  const { t } = useLang();
  const now = useNow();
  const summary = usePolling(() => partnerSummary(apiKey), 10_000);
  const campaigns = usePolling(() => partnerCampaigns(apiKey), 10_000);
  const blocklist = usePolling(() => partnerBlocklist(apiKey), 10_000);
  const [csvError, setCsvError] = useState(false);
  const s = summary.data;
  const offline = summary.error || campaigns.error || blocklist.error;
  const scope = info.brand ?? t("pt.all_brands");

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{info.name}</h1>
          <p className="text-ink2">{t("pt.shown")} <b className="text-ink">{scope}</b>. {t("pt.only_own")}</p>
        </div>
        <button type="button" onClick={onLogout} className="rounded-lg border border-line bg-surface px-3 py-1.5 text-sm hover:bg-page">{t("pt.logout")}</button>
      </div>

      {offline && <Notice tone="warn">{s ? t("pt.offline_stale") : t("pt.offline")}</Notice>}

      <section aria-label={t("pt.kpi.aria")} className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label={t("pt.kpi.reports")} value={s?.reports_total ?? "…"} hint={t("pt.kpi.reports_hint", { n: s?.reports_last_24h ?? "…" })} />
        <StatTile label={t("pt.kpi.campaigns")} value={s?.campaigns ?? "…"} hint={t("pt.kpi.campaigns_hint")} />
        <StatTile label={t("pt.kpi.active")} value={s?.campaigns_active_24h ?? "…"} hint={t("pt.kpi.active_hint")} />
        <StatTile label={t("pt.kpi.domains")} value={s?.blocklist_domains ?? "…"} hint={t("pt.kpi.domains_hint")} />
      </section>

      {info.webhook && <Notice>{t("pt.webhook")}</Notice>}

      <section aria-label={t("pt.camp.aria")} className="space-y-3">
        <SectionTitle hint={t("pt.camp.hint")}>{t("dash.camp.title")}</SectionTitle>
        {!campaigns.data && !campaigns.error && <Loading className="!py-6" />}
        {campaigns.data?.length === 0 && <Card><p className="text-sm text-ink2">{t("pt.camp.empty")}</p></Card>}
        {campaigns.data?.map((c) => <CampaignCard key={c.id} campaign={c} now={now} />)}
      </section>

      <section aria-label={t("dash.bl.aria")}>
        <SectionTitle
          hint={t("pt.bl.hint")}
          right={
            <button
              type="button"
              onClick={() => downloadPartnerCsv(apiKey).then(() => setCsvError(false)).catch(() => setCsvError(true))}
              className="rounded-lg border border-line bg-surface px-3 py-1.5 text-sm font-medium hover:bg-page"
            >
              {t("common.csv")}
            </button>
          }
        >
          {t("dash.bl.title")}
        </SectionTitle>
        {csvError && <Notice tone="warn">{t("err.csv")}</Notice>}
        <Card className="!p-0"><BlocklistTable rows={blocklist.data ?? []} now={now} /></Card>
        <p className="mt-2 text-xs text-ink2">{t("dash.bl.note")}</p>
      </section>
    </div>
  );
}
