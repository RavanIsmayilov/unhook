"use client";

import { useState } from "react";
import { Card, Chip, Notice, SectionTitle, StatTile, tint, VERDICT_META } from "@/components/ui";
import { checkErrorMessage, getChallengeStats, sendChallenge } from "@/lib/api";
import { pct, timeAgo } from "@/lib/format";
import type { CheckResult } from "@/lib/types";
import { useNow, usePolling } from "@/lib/usePolling";

const MAX = 1000;

export default function Challenge() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<CheckResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const stats = usePolling(getChallengeStats, 10_000);
  const now = useNow();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim() || busy) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await sendChallenge(text));
    } catch (err) {
      setError(checkErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const s = stats.data;
  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div className="text-center">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">🎮 Unhook-u aldada bilərsən?</h1>
        <p className="mt-2 text-ink2">
          Real fırıldaq mesajı kimi yaz (bonus, bank, iş, bağlama...), amma elə yaz ki, Unhook onu <b className="text-ink">tanımasın</b>.
          Aldadan mesajlar test nümunəsinə çevrilir və sistem onlardan öyrənir.
        </p>
      </div>

      <form onSubmit={submit} className="space-y-3 rounded-2xl border border-line bg-surface p-4 sm:p-5">
        <label htmlFor="attempt" className="block text-sm font-semibold">Sənin fırıldaq mesajın</label>
        <textarea
          id="attempt"
          rows={5}
          value={text}
          onChange={(e) => setText(e.target.value.slice(0, MAX))}
          placeholder="Məsələn: translitlə yaz, rus sözləri qat, linksiz yaz, rəsmi ton işlət..."
          className="w-full resize-y rounded-xl border border-line bg-page px-3 py-2.5 text-base placeholder:text-muted"
        />
        <div className="flex items-center justify-between text-xs text-ink2">
          <span>Mesajlar yalnız test üçün saxlanır və real hesabatlara qarışmır.</span>
          <span className="tabular-nums">{text.length}/{MAX}</span>
        </div>
        <button
          type="submit"
          disabled={busy || !text.trim()}
          className="min-h-12 w-full rounded-xl bg-s1 px-4 py-3 text-base font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? "Yoxlayıram..." : "Cəhd et"}
        </button>
      </form>

      <div aria-live="polite" className="space-y-3">
        {error && <Notice tone="warn">{error}</Notice>}
        {result && <Outcome result={result} />}
      </div>

      <section aria-label="Nəticələr">
        <SectionTitle hint="Hamının cəhdləri">Skorbord</SectionTitle>
        <div className="grid grid-cols-3 gap-3">
          <StatTile label="Cəhd" value={s?.attempts ?? 0} />
          <StatTile label="Aldadan" value={s?.fooled ?? 0} hint={s?.fooled_rate != null ? `${pct(s.fooled_rate)} cəhd` : undefined} />
          <StatTile label="Tutulan" value={s?.caught ?? 0} hint={s?.unsure ? `${s.unsure} şübhəli` : undefined} />
        </div>
        <Card className="mt-3 !p-0">
          <h3 className="border-b border-grid px-4 py-3 text-sm font-semibold">Unhook-u aldadan mesajlar</h3>
          {s && s.fooled_examples.length > 0 ? (
            <ul className="divide-y divide-grid">
              {s.fooled_examples.map((x) => (
                <li key={x.id} className="px-4 py-3">
                  <p className="text-sm">{x.text}</p>
                  <p className="mt-1 text-xs text-ink2">{timeAgo(x.created_at, now)}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="p-4 text-sm text-ink2">Hələ heç kim aldada bilməyib. Birinci sən ol!</p>
          )}
        </Card>
      </section>
    </div>
  );
}

function Outcome({ result }: { result: CheckResult }) {
  if (result.degraded) {
    return <Notice tone="warn">AI hazırda cavab verə bilmədi, cəhd sayılmadı. Bir az sonra yenidən yoxla.</Notice>;
  }
  const meta = VERDICT_META[result.verdict];
  const headline =
    result.verdict === "safe" ? "🎉 Aldatdın! Unhook bunu təhlükəsiz saydı."
    : result.verdict === "suspicious" ? "🟡 Az qala! Unhook bunu şübhəli saydı."
    : "🔴 Tutuldu! Unhook bunu fırıldaq saydı.";
  return (
    <div className="rounded-2xl border border-line p-4" style={{ background: tint(meta.color, 10) }}>
      <h2 className="text-lg font-bold">{headline}</h2>
      {result.scheme !== "none" && <div className="mt-2"><Chip>📌 {result.scheme_az}</Chip></div>}
      {result.verdict !== "safe" && result.reasons.length > 0 && (
        <>
          <p className="mt-3 text-sm font-semibold">Niyə tutdu?</p>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-ink2">{result.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
        </>
      )}
      {result.verdict === "safe" && <p className="mt-2 text-sm text-ink2">Bu mesaj test nümunəsi kimi saxlanıldı. Təşəkkür edirik!</p>}
    </div>
  );
}
