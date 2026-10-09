"use client";

import { BarList, ChartCard, Legend, type BarRow } from "@/components/charts";
import { Card, Chip, Notice, SectionTitle } from "@/components/ui";
import { getResults } from "@/lib/api";
import { pct } from "@/lib/format";
import type { AttackResults, EvalResults, EvalSystem } from "@/lib/types";
import { usePolling } from "@/lib/usePolling";

const WRITING_AZ: Record<string, string> = { az: "Azərbaycan", translit: "Translit", az_ru: "AZ + RU" };
const TECHNIQUE_AZ: Record<string, string> = {
  translit: "Translit (ə, ş, ç olmadan)",
  az_ru: "Azərbaycan + rus qarışıq",
  synonyms: "Sinonimlər",
  new_pretext: "Yeni bəhanə",
  typos: "Yazı səhvləri",
  no_link: "Linksiz",
  formal_tone: "Rəsmi ton",
  short_sms: "Qısa SMS",
};

/** Color follows the system, never its rank: baseline is gray, Groq blue, Gemini orange. */
function systemColor(s: EvalSystem): string {
  if (s.kind === "baseline") return "var(--mark-gray)";
  return s.key === "gemini" ? "var(--series-2)" : "var(--series-1)";
}

function systemName(s: EvalSystem): string {
  return s.kind === "baseline" ? "Açar-söz filtri" : `Unhook (${s.key === "gemini" ? "Gemini" : s.key === "groq" ? "Groq" : s.key})`;
}

export default function Results() {
  const { data, error } = usePolling(getResults, 30_000);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Nəticələr</h1>
        <p className="text-ink2">Unhook sadə açar-söz filtrindən nə qədər yaxşıdır? Rəqəmlər real ölçmədən gəlir (<code>eval.py</code> və <code>attacker.py</code>).</p>
      </div>

      {error && <Notice tone="warn">Nəticələri yükləmək mümkün olmadı. Backend işləyirmi?</Notice>}
      {!data && !error && <p className="text-ink2">Yüklənir...</p>}

      {data && (
        <>
          {data.eval ? <EvalSection ev={data.eval} /> : <Notice>Qiymətləndirmə hələ işlədilməyib: <code>python eval.py --providers groq</code></Notice>}
          {data.attack ? <AttackSection at={data.attack} /> : <Notice>Hücum testi hələ işlədilməyib: <code>python attacker.py</code></Notice>}
          <Caveats />
        </>
      )}
    </div>
  );
}

/** A system that failed to answer more than 10% of the messages is not comparable, so it is left out of the charts. */
const isComplete = (s: EvalSystem) => s.metrics.n_degraded <= 0.1 * s.metrics.n;

function EvalSection({ ev: all }: { ev: EvalResults }) {
  const ev = { ...all, systems: all.systems.filter(isComplete) };
  const incomplete = all.systems.filter((s) => !isComplete(s));
  const first = ev.systems[0].metrics;
  const legend = ev.systems.map((s) => ({ label: systemName(s), color: systemColor(s) }));
  const rows = (pick: (s: EvalSystem) => number | null): BarRow[] =>
    ev.systems.map((s) => {
      const v = pick(s);
      return { label: systemName(s), value: v ?? 0, display: pct(v, 1), color: systemColor(s), sub: s.metrics.n_degraded ? `⚠ ${s.metrics.n_degraded} sətir cavabsız` : undefined };
    });

  return (
    <section className="space-y-4" aria-label="Qiymətləndirmə">
      <SectionTitle hint={`${ev.n_rows} mesaj: ${first.n_scam} fırıldaq, ${first.n_safe} təhlükəsiz. Hər mesaj 3 yazılışda (az, translit, az+rus).`}>
        Sistemimiz və açar-söz filtri
      </SectionTitle>
      {incomplete.length > 0 && (
        <Notice tone="warn">
          ⚠ Müqayisəyə daxil edilməyib: {incomplete.map((s) => `${systemName(s)} (${s.metrics.n - s.metrics.n_degraded} / ${s.metrics.n} mesaj cavablandı, qalanı üçün pulsuz API limiti bitib)`).join("; ")}. Natamam nəticəni tam nəticə ilə yan-yana qoymaq yanıldıcı olardı.
        </Notice>
      )}
      <Legend items={legend} />
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Fırıldaqların tapılması"
          note="Fırıldaq mesajlarının neçə faizi xəbərdarlıq aldı. Yüksək yaxşıdır."
          table={tableOf(ev, ["Recall (xəbərdarlıq)", "Recall (yalnız “fırıldaq”)"], (m) => [pct(m.recall_flagged, 1), pct(m.recall_strict, 1)])}
        >
          <BarList rows={rows((s) => s.metrics.recall_flagged)} max={1} />
        </ChartCard>
        <ChartCard
          title="Yanlış həyəcan"
          note="Təhlükəsiz mesajların neçə faizi səhvən xəbərdarlıq aldı. Aşağı yaxşıdır."
          table={tableOf(ev, ["Yanlış həyəcan (xəbərdarlıq)", "Yanlış həyəcan (yalnız “fırıldaq”)"], (m) => [pct(m.fpr_flagged, 1), pct(m.fpr_strict, 1)])}
        >
          <BarList rows={rows((s) => s.metrics.fpr_flagged)} max={1} />
        </ChartCard>
      </div>

      <Card>
        <h3 className="mb-1 font-semibold">Translit və rus qarışıq yazılışlar</h3>
        <p className="mb-3 text-sm text-ink2">Eyni mesajın üç yazılışı: tapılma faizi və eyni verdikt verilmə dərəcəsi.</p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-ink2">
                <th className="py-1.5 pr-4 font-medium">Sistem</th>
                {Object.values(WRITING_AZ).map((w) => <th key={w} className="py-1.5 pr-4 font-medium">{w}</th>)}
                <th className="py-1.5 font-medium">Eyni verdikt</th>
              </tr>
            </thead>
            <tbody>
              {ev.systems.map((s) => (
                <tr key={s.key} className="border-b border-grid last:border-0">
                  <td className="py-2 pr-4 font-medium"><span className="mr-2 inline-block h-2.5 w-2.5 rounded-sm align-middle" style={{ background: systemColor(s) }} aria-hidden />{systemName(s)}</td>
                  {Object.keys(WRITING_AZ).map((w) => <td key={w} className="py-2 pr-4 tabular-nums">{pct(s.metrics.recall_flagged_by_variant[w], 1)}</td>)}
                  <td className="py-2 tabular-nums">{s.metrics.consistency_groups ? `${pct(s.metrics.consistency_verdict, 0)} (${s.metrics.consistency_groups} qrup)` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <FailureDetails ev={ev} />
    </section>
  );
}

function tableOf(ev: EvalResults, head: string[], cells: (m: EvalSystem["metrics"]) => string[]) {
  return { head: ["Sistem", ...head, "Qiymətləndirilən"], rows: ev.systems.map((s) => [systemName(s), ...cells(s.metrics), s.metrics.n - s.metrics.n_degraded]) };
}

function FailureDetails({ ev }: { ev: EvalResults }) {
  return (
    <Card>
      <h3 className="mb-1 font-semibold">Səhv proqnozlar</h3>
      <p className="mb-3 text-sm text-ink2">Gizlətmirik: hər sistemin səhv etdiyi mesajlar.</p>
      <div className="space-y-2">
        {ev.systems.map((s) => {
          const f = ev.failures[s.key];
          return (
            <details key={s.key} className="rounded-xl border border-line px-3 py-2">
              <summary className="cursor-pointer text-sm font-medium">{systemName(s)}: {f.total} səhv / {ev.n_rows}</summary>
              {f.total === 0 ? (
                <p className="mt-2 text-sm text-ink2">Səhv proqnoz yoxdur.</p>
              ) : (
                <ul className="mt-2 space-y-2 text-sm">
                  {f.items.map((x) => (
                    <li key={x.id} className="border-t border-grid pt-2">
                      <div className="flex flex-wrap items-center gap-2"><Chip mono>{x.id}</Chip><span className="text-xs text-ink2">{x.type}</span></div>
                      <p className="mt-1 text-ink2">{x.text}</p>
                    </li>
                  ))}
                  {f.total > f.items.length && <li className="text-xs text-ink2">… və daha {f.total - f.items.length} (tam siyahı: results/failures.md)</li>}
                </ul>
              )}
            </details>
          );
        })}
      </div>
    </Card>
  );
}

function AttackSection({ at }: { at: AttackResults }) {
  const techniqueRows: BarRow[] = at.by_technique.map((t) => ({
    label: TECHNIQUE_AZ[t.technique] ?? t.technique,
    value: t.detected_flagged ?? 0,
    display: pct(t.detected_flagged),
    sub: t.missed ? `${t.missed} qaçırıldı` : undefined,
  }));
  const ho = at.heldout_before && at.heldout_after;

  return (
    <section className="space-y-4" aria-label="Hücum testi">
      <SectionTitle hint={`Hücumçu: ${at.config.attacker_model}. Analizator: ${at.config.analyzer_model}. ${at.overall.n} yeni variant, ${at.config.n_seeds} əsas mesajdan.`}>
        Hücumçu agent: analizatoru aldatmağa çalışır
      </SectionTitle>
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Hücum variantlarının tapılması"
          note={`Ümumi: ${pct(at.overall.detected_flagged)} tapıldı, ${at.overall.missed} qaçırıldı.`}
          table={{ head: ["Üsul", "Variant", "Tapıldı", "Qaçırıldı"], rows: at.by_technique.map((t) => [TECHNIQUE_AZ[t.technique] ?? t.technique, t.n, pct(t.detected_flagged), t.missed]) }}
        >
          <BarList rows={techniqueRows} max={1} />
        </ChartCard>

        {ho ? (
          <ChartCard
            title="Qaçırılanları nümunə əlavə etdikdən sonra"
            note={`${at.fewshot.length} qaçırılmış variant promta əlavə edildi. Ölçmə yalnız əlavə edilməyən ${at.heldout_before!.n} variantdadır.`}
            table={{
              head: ["Göstərici", "Əvvəl", "Sonra"],
              rows: [
                ["Tapılma", pct(at.heldout_before!.detected_flagged), pct(at.heldout_after!.detected_flagged)],
                ...(at.false_positives_before && at.false_positives_after
                  ? [["Yanlış həyəcan", pct(at.false_positives_before.fpr_flagged), pct(at.false_positives_after.fpr_flagged)]]
                  : []),
              ],
            }}
          >
            <Legend items={[{ label: "Əvvəl", color: "var(--mark-gray)" }, { label: "Sonra", color: "var(--series-1)" }]} />
            <BarList
              rows={[
                { label: "Tapılma: əvvəl", value: at.heldout_before!.detected_flagged ?? 0, display: pct(at.heldout_before!.detected_flagged), color: "var(--mark-gray)" },
                { label: "Tapılma: sonra", value: at.heldout_after!.detected_flagged ?? 0, display: pct(at.heldout_after!.detected_flagged), color: "var(--series-1)" },
                ...(at.false_positives_before && at.false_positives_after
                  ? [
                      { label: "Yanlış həyəcan: əvvəl", value: at.false_positives_before.fpr_flagged ?? 0, display: pct(at.false_positives_before.fpr_flagged), color: "var(--mark-gray)" },
                      { label: "Yanlış həyəcan: sonra", value: at.false_positives_after.fpr_flagged ?? 0, display: pct(at.false_positives_after.fpr_flagged), color: "var(--series-1)" },
                    ]
                  : []),
              ]}
              max={1}
            />
          </ChartCard>
        ) : (
          <Card>
            <h3 className="font-semibold">Əvvəl və sonra</h3>
            <p className="mt-1 text-sm text-ink2">
              {at.overall.missed === 0
                ? "Heç bir variant qaçırılmadı: analizator bu hücuma dözdü."
                : "Müqayisə üçün ən azı 2 qaçırılmış variant lazımdır. Daha çox mesaj və variantla yenidən işlədin."}
            </p>
          </Card>
        )}
      </div>

      {at.misses.length > 0 && (
        <Card>
          <h3 className="mb-1 font-semibold">Qaçırılan variantlar ({at.overall.missed})</h3>
          <p className="mb-3 text-sm text-ink2">Analizatorun “təhlükəsiz” dediyi hücum variantları. Bunlar test nümunələrinə çevrilir (<code>data/attack_misses.csv</code>).</p>
          <ul className="space-y-2 text-sm">
            {at.misses.map((m) => (
              <li key={m.id} className="border-t border-grid pt-2 first:border-0 first:pt-0">
                <div className="flex flex-wrap items-center gap-2"><Chip mono>{m.id}</Chip><Chip>{TECHNIQUE_AZ[m.technique] ?? m.technique}</Chip></div>
                <p className="mt-1 text-ink2">{m.text}</p>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </section>
  );
}

function Caveats() {
  return (
    <Card>
      <h3 className="mb-2 font-semibold">Metodologiya və məhdudiyyətlər</h3>
      <ul className="list-disc space-y-1 pl-5 text-sm text-ink2 marker:text-muted">
        <li>Test mesajlarını AI (Claude) yazıb, yəni sintetikdir və real dələduz mesajlarından fərqli ola bilər.</li>
        <li>Nümunə sayı kiçikdir. Faizlər dəqiq ölçü yox, istiqamət göstəricisidir.</li>
        <li>“Xəbərdarlıq” = “fırıldaq” və ya “şübhəli” verdikt. “Yalnız fırıldaq” daha sərt ölçüdür.</li>
        <li>Hücum variantlarını da LLM yazır və etiketlər insan tərəfindən yoxlanmayıb.</li>
        <li>Açar-söz filtri: bonus, kart, kod, təcili, link və s. sözlərə baxan sadə baza xətti.</li>
      </ul>
    </Card>
  );
}
