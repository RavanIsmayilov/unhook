"use client";

import { BarList, ChartCard, Legend, type BarRow } from "@/components/charts";
import { Card, Chip, Notice, SectionTitle, StatTile } from "@/components/ui";
import { getResults } from "@/lib/api";
import { pct } from "@/lib/format";
import { useLang, type TFunction } from "@/lib/i18n";
import type { MessageKey } from "@/lib/messages/az";
import type { AttackResults, EvalResults, EvalSystem, PerformanceResults } from "@/lib/types";
import { usePolling } from "@/lib/usePolling";

const WRITINGS = ["az", "translit", "az_ru"] as const;

/** Color follows the system, never its rank: baseline is gray, Groq blue, Gemini orange. */
function systemColor(s: EvalSystem): string {
  if (s.kind === "baseline") return "var(--mark-gray)";
  return s.key === "gemini" ? "var(--series-2)" : "var(--series-1)";
}

function systemName(t: TFunction, s: EvalSystem): string {
  if (s.kind === "baseline") return t("res.sys.baseline");
  return t("res.sys.unhook", { name: s.key === "gemini" ? "Gemini" : s.key === "groq" ? "Groq" : s.key });
}

/** The API names failure types in English; show them in the visitor's language. */
function failureType(t: TFunction, raw: string): string {
  const r = raw.toLowerCase();
  if (r.startsWith("missed")) return t("res.ft.missed");
  if (r.startsWith("weak")) return t("res.ft.weak");
  if (r.startsWith("false alarm")) return t("res.ft.false_alarm");
  if (r.startsWith("soft false alarm")) return t("res.ft.soft_alarm");
  if (r.startsWith("no model answer")) return t("res.ft.degraded");
  return raw;
}

export default function Results() {
  const { t } = useLang();
  const { data, error } = usePolling(getResults, 30_000);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{t("res.title")}</h1>
        <p className="text-ink2">{t("res.lead")}</p>
      </div>

      {error && <Notice tone="warn">{t("res.error")}</Notice>}
      {!data && !error && <p className="text-ink2">{t("common.loading")}</p>}

      {data && (
        <>
          {data.eval ? <EvalSection ev={data.eval} /> : <Notice>{t("res.no_eval")}</Notice>}
          {data.attack ? <AttackSection at={data.attack} /> : <Notice>{t("res.no_attack")}</Notice>}
          {data.performance && <PerformanceSection p={data.performance} />}
          <Caveats />
        </>
      )}
    </div>
  );
}

/** A system that failed to answer more than 10% of the messages is not comparable, so it is left out of the charts. */
const isComplete = (s: EvalSystem) => s.metrics.n_degraded <= 0.1 * s.metrics.n;

function EvalSection({ ev: all }: { ev: EvalResults }) {
  const { t } = useLang();
  const ev = { ...all, systems: all.systems.filter(isComplete) };
  const incomplete = all.systems.filter((s) => !isComplete(s));
  const first = ev.systems[0].metrics;
  const legend = ev.systems.map((s) => ({ label: systemName(t, s), color: systemColor(s) }));
  const rows = (pick: (s: EvalSystem) => number | null): BarRow[] =>
    ev.systems.map((s) => {
      const v = pick(s);
      return {
        label: systemName(t, s), value: v ?? 0, display: pct(v, 1), color: systemColor(s),
        sub: s.metrics.n_degraded ? t("res.unanswered", { n: s.metrics.n_degraded }) : undefined,
      };
    });
  const tableOf = (head: string[], cells: (m: EvalSystem["metrics"]) => string[]) => ({
    head: [t("res.th.system"), ...head, t("res.th.scored")],
    rows: ev.systems.map((s) => [systemName(t, s), ...cells(s.metrics), s.metrics.n - s.metrics.n_degraded]),
  });

  return (
    <section className="space-y-4" aria-label={t("res.eval.aria")}>
      <SectionTitle hint={t("res.eval.hint", { n: ev.n_rows, scam: first.n_scam, safe: first.n_safe })}>{t("res.eval.title")}</SectionTitle>
      {incomplete.length > 0 && (
        <Notice tone="warn">
          {t("res.eval.incomplete", {
            list: incomplete.map((s) => t("res.eval.incomplete_item", { name: systemName(t, s), done: s.metrics.n - s.metrics.n_degraded, n: s.metrics.n })).join("; "),
          })}
        </Notice>
      )}
      <Legend items={legend} />
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title={t("res.recall.title")}
          note={t("res.recall.note")}
          table={tableOf([t("res.th.recall_flag"), t("res.th.recall_strict")], (m) => [pct(m.recall_flagged, 1), pct(m.recall_strict, 1)])}
        >
          <BarList rows={rows((s) => s.metrics.recall_flagged)} max={1} />
        </ChartCard>
        <ChartCard
          title={t("res.fpr.title")}
          note={t("res.fpr.note")}
          table={tableOf([t("res.th.fpr_flag"), t("res.th.fpr_strict")], (m) => [pct(m.fpr_flagged, 1), pct(m.fpr_strict, 1)])}
        >
          <BarList rows={rows((s) => s.metrics.fpr_flagged)} max={1} />
        </ChartCard>
      </div>

      <Card>
        <h3 className="mb-1 font-semibold">{t("res.writing.title")}</h3>
        <p className="mb-3 text-sm text-ink2">{t("res.writing.lead")}</p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-ink2">
                <th className="py-1.5 pr-4 font-medium">{t("res.th.system")}</th>
                {WRITINGS.map((w) => <th key={w} className="py-1.5 pr-4 font-medium">{t(`res.writing.${w}`)}</th>)}
                <th className="py-1.5 font-medium">{t("res.writing.same")}</th>
              </tr>
            </thead>
            <tbody>
              {ev.systems.map((s) => (
                <tr key={s.key} className="border-b border-grid last:border-0">
                  <td className="py-2 pr-4 font-medium"><span className="mr-2 inline-block h-2.5 w-2.5 rounded-sm align-middle" style={{ background: systemColor(s) }} aria-hidden />{systemName(t, s)}</td>
                  {WRITINGS.map((w) => <td key={w} className="py-2 pr-4 tabular-nums">{pct(s.metrics.recall_flagged_by_variant[w], 1)}</td>)}
                  <td className="py-2 tabular-nums">{s.metrics.consistency_groups ? t("res.writing.groups", { pct: pct(s.metrics.consistency_verdict, 0), n: s.metrics.consistency_groups }) : "—"}</td>
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

function FailureDetails({ ev }: { ev: EvalResults }) {
  const { t } = useLang();
  return (
    <Card>
      <h3 className="mb-1 font-semibold">{t("res.fail.title")}</h3>
      <p className="mb-3 text-sm text-ink2">{t("res.fail.lead")}</p>
      <div className="space-y-2">
        {ev.systems.map((s) => {
          const f = ev.failures[s.key];
          return (
            <details key={s.key} className="rounded-xl border border-line px-3 py-2">
              <summary className="cursor-pointer text-sm font-medium">{t("res.fail.summary", { name: systemName(t, s), n: f.total, total: ev.n_rows })}</summary>
              {f.total === 0 ? (
                <p className="mt-2 text-sm text-ink2">{t("res.fail.none")}</p>
              ) : (
                <ul className="mt-2 space-y-2 text-sm">
                  {f.items.map((x) => (
                    <li key={x.id} className="border-t border-grid pt-2">
                      <div className="flex flex-wrap items-center gap-2"><Chip mono>{x.id}</Chip><span className="text-xs text-ink2">{failureType(t, x.type)}</span></div>
                      <p className="mt-1 text-ink2">{x.text}</p>
                    </li>
                  ))}
                  {f.total > f.items.length && <li className="text-xs text-ink2">{t("res.fail.more", { n: f.total - f.items.length })}</li>}
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
  const { t } = useLang();
  const tech = (name: string) => (name in TECH ? t(TECH[name]) : name);
  const techniqueRows: BarRow[] = at.by_technique.map((x) => ({
    label: tech(x.technique),
    value: x.detected_flagged ?? 0,
    display: pct(x.detected_flagged),
    sub: x.missed ? t("res.atk.missed_sub", { n: x.missed }) : undefined,
  }));
  const ho = at.heldout_before && at.heldout_after;
  const fpPair = at.false_positives_before && at.false_positives_after;

  return (
    <section className="space-y-4" aria-label={t("res.atk.aria")}>
      <SectionTitle hint={t("res.atk.hint", { attacker: at.config.attacker_model, analyzer: at.config.analyzer_model, n: at.overall.n, seeds: at.config.n_seeds })}>
        {t("res.atk.title")}
      </SectionTitle>
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title={t("res.atk.detect.title")}
          note={t("res.atk.detect.note", { pct: pct(at.overall.detected_flagged), missed: at.overall.missed })}
          table={{
            head: [t("res.atk.th.technique"), t("res.atk.th.variants"), t("res.atk.th.found"), t("res.atk.th.missed")],
            rows: at.by_technique.map((x) => [tech(x.technique), x.n, pct(x.detected_flagged), x.missed]),
          }}
        >
          <BarList rows={techniqueRows} max={1} />
        </ChartCard>

        {ho ? (
          <ChartCard
            title={t("res.atk.after.title")}
            note={t("res.atk.after.note", { k: at.fewshot.length, n: at.heldout_before!.n })}
            table={{
              head: [t("res.atk.metric"), t("res.atk.before"), t("res.atk.after")],
              rows: [
                [t("res.atk.found"), pct(at.heldout_before!.detected_flagged), pct(at.heldout_after!.detected_flagged)],
                ...(fpPair ? [[t("res.atk.fp"), pct(at.false_positives_before!.fpr_flagged), pct(at.false_positives_after!.fpr_flagged)]] : []),
              ],
            }}
          >
            <Legend items={[{ label: t("res.atk.before"), color: "var(--mark-gray)" }, { label: t("res.atk.after"), color: "var(--series-1)" }]} />
            <BarList
              rows={[
                { label: `${t("res.atk.found")}: ${t("res.atk.before")}`, value: at.heldout_before!.detected_flagged ?? 0, display: pct(at.heldout_before!.detected_flagged), color: "var(--mark-gray)" },
                { label: `${t("res.atk.found")}: ${t("res.atk.after")}`, value: at.heldout_after!.detected_flagged ?? 0, display: pct(at.heldout_after!.detected_flagged), color: "var(--series-1)" },
                ...(fpPair
                  ? [
                      { label: `${t("res.atk.fp")}: ${t("res.atk.before")}`, value: at.false_positives_before!.fpr_flagged ?? 0, display: pct(at.false_positives_before!.fpr_flagged), color: "var(--mark-gray)" },
                      { label: `${t("res.atk.fp")}: ${t("res.atk.after")}`, value: at.false_positives_after!.fpr_flagged ?? 0, display: pct(at.false_positives_after!.fpr_flagged), color: "var(--series-1)" },
                    ]
                  : []),
              ]}
              max={1}
            />
          </ChartCard>
        ) : (
          <Card>
            <h3 className="font-semibold">{t("res.atk.before_after.title")}</h3>
            <p className="mt-1 text-sm text-ink2">{at.overall.missed === 0 ? t("res.atk.none_missed") : t("res.atk.too_few")}</p>
          </Card>
        )}
      </div>

      {at.misses.length > 0 && (
        <Card>
          <h3 className="mb-1 font-semibold">{t("res.atk.misses.title", { n: at.overall.missed })}</h3>
          <p className="mb-3 text-sm text-ink2">{t("res.atk.misses.lead")}</p>
          <ul className="space-y-2 text-sm">
            {at.misses.map((m) => (
              <li key={m.id} className="border-t border-grid pt-2 first:border-0 first:pt-0">
                <div className="flex flex-wrap items-center gap-2"><Chip mono>{m.id}</Chip><Chip>{tech(m.technique)}</Chip></div>
                <p className="mt-1 text-ink2">{m.text}</p>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </section>
  );
}

const TECH: Record<string, MessageKey> = {
  translit: "tech.translit",
  az_ru: "tech.az_ru",
  synonyms: "tech.synonyms",
  new_pretext: "tech.new_pretext",
  typos: "tech.typos",
  no_link: "tech.no_link",
  formal_tone: "tech.formal_tone",
  short_sms: "tech.short_sms",
};

function PerformanceSection({ p }: { p: PerformanceResults }) {
  const { t } = useLang();
  const sec = (ms: number | null) => (ms == null ? "—" : t("common.seconds", { n: (ms / 1000).toFixed(1) }));
  return (
    <section className="space-y-3" aria-label={t("res.perf.aria")}>
      <SectionTitle hint={t("res.perf.hint", { n: p.n_messages, model: p.model })}>{t("res.perf.title")}</SectionTitle>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label={t("res.perf.median")} value={sec(p.model_ms_p50)} />
        <StatTile label={t("res.perf.p95")} value={sec(p.model_ms_p95)} hint={t("res.perf.p95_hint")} />
        <StatTile label={t("res.perf.tokens")} value={`${p.tokens_in_avg} / ${p.tokens_out_avg}`} />
        <StatTile
          label={t("res.perf.cost")}
          value={p.cost_per_check_usd == null ? "—" : `$${p.cost_per_check_usd.toFixed(5)}`}
          hint={p.cost_per_1000_checks_usd == null ? undefined : t("res.perf.cost_hint", { x: p.cost_per_1000_checks_usd.toFixed(2) })}
        />
      </div>
      <p className="text-sm text-ink2">
        {t("res.perf.note", { in: p.price_input_per_m ?? "—", out: p.price_output_per_m ?? "—", source: p.price_source ?? "—" })}
      </p>
    </section>
  );
}

function Caveats() {
  const { t } = useLang();
  return (
    <Card>
      <h3 className="mb-2 font-semibold">{t("res.cav.title")}</h3>
      <ul className="list-disc space-y-1 pl-5 text-sm text-ink2 marker:text-muted">
        <li>{t("res.cav.1")}</li>
        <li>{t("res.cav.2")}</li>
        <li>{t("res.cav.3")}</li>
        <li>{t("res.cav.4")}</li>
        <li>{t("res.cav.5")}</li>
      </ul>
    </Card>
  );
}
