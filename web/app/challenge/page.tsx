"use client";

import { useState } from "react";
import { Card, Chip, Notice, SectionTitle, StatTile, VERDICT_STYLE, tint } from "@/components/ui";
import { checkErrorMessage, getChallengeStats, sendChallenge } from "@/lib/api";
import { pct, timeAgo } from "@/lib/format";
import { schemeLabel, useLang } from "@/lib/i18n";
import type { CheckResult } from "@/lib/types";
import { useNow, usePolling } from "@/lib/usePolling";

const MAX = 1000;

export default function Challenge() {
  const { t, lang } = useLang();
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
      setResult(await sendChallenge(text, lang));
    } catch (err) {
      setError(checkErrorMessage(err, t));
    } finally {
      setBusy(false);
    }
  }

  const s = stats.data;
  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div className="text-center">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{t("ch.title")}</h1>
        <p className="mt-2 text-ink2">{t("ch.lead")}</p>
      </div>

      <form onSubmit={submit} className="space-y-3 rounded-2xl border border-line bg-surface p-4 sm:p-5">
        <label htmlFor="attempt" className="block text-sm font-semibold">{t("ch.label")}</label>
        <textarea
          id="attempt"
          rows={5}
          value={text}
          onChange={(e) => setText(e.target.value.slice(0, MAX))}
          placeholder={t("ch.placeholder")}
          className="w-full resize-y rounded-xl border border-line bg-page px-3 py-2.5 text-base placeholder:text-muted"
        />
        <div className="flex items-center justify-between text-xs text-ink2">
          <span>{t("ch.note")}</span>
          <span className="tabular-nums">{text.length}/{MAX}</span>
        </div>
        <button
          type="submit"
          disabled={busy || !text.trim()}
          className="min-h-12 w-full rounded-xl bg-s1 px-4 py-3 text-base font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? t("ch.busy") : t("ch.submit")}
        </button>
      </form>

      <div aria-live="polite" className="space-y-3">
        {error && <Notice tone="warn">{error}</Notice>}
        {result && <Outcome result={result} />}
      </div>

      <section aria-label={t("ch.board.aria")}>
        <SectionTitle hint={t("ch.board.hint")}>{t("ch.board.title")}</SectionTitle>
        <div className="grid grid-cols-3 gap-3">
          <StatTile label={t("ch.attempts")} value={s?.attempts ?? 0} />
          <StatTile label={t("ch.fooled")} value={s?.fooled ?? 0} hint={s?.fooled_rate != null ? t("ch.fooled_hint", { pct: pct(s.fooled_rate) }) : undefined} />
          <StatTile label={t("ch.caught")} value={s?.caught ?? 0} hint={s?.unsure ? t("ch.caught_hint", { n: s.unsure }) : undefined} />
        </div>
        <Card className="mt-3 !p-0">
          <h3 className="border-b border-grid px-4 py-3 text-sm font-semibold">{t("ch.fooled_list")}</h3>
          {s && s.fooled_examples.length > 0 ? (
            <ul className="divide-y divide-grid">
              {s.fooled_examples.map((x) => (
                <li key={x.id} className="px-4 py-3">
                  <p className="text-sm">{x.text}</p>
                  <p className="mt-1 text-xs text-ink2">{timeAgo(x.created_at, now, t)}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="p-4 text-sm text-ink2">{t("ch.fooled_empty")}</p>
          )}
        </Card>
      </section>
    </div>
  );
}

function Outcome({ result }: { result: CheckResult }) {
  const { t } = useLang();
  if (result.degraded) return <Notice tone="warn">{t("ch.out.degraded")}</Notice>;
  const meta = VERDICT_STYLE[result.verdict];
  return (
    <div className="rounded-2xl border border-line p-4" style={{ background: tint(meta.color, 10) }}>
      <h2 className="text-lg font-bold">{t(`ch.out.${result.verdict === "safe" ? "safe" : result.verdict}`)}</h2>
      {result.scheme !== "none" && <div className="mt-2"><Chip>📌 {schemeLabel(t, result.scheme)}</Chip></div>}
      {result.verdict !== "safe" && result.reasons.length > 0 && (
        <>
          <p className="mt-3 text-sm font-semibold">{t("ch.out.why")}</p>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-ink2">{result.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
        </>
      )}
      {result.verdict === "safe" && <p className="mt-2 text-sm text-ink2">{t("ch.out.saved")}</p>}
    </div>
  );
}
