"use client";

import { pct } from "@/lib/format";
import { schemeLabel, tipsFor, useLang } from "@/lib/i18n";
import type { MessageKey } from "@/lib/messages/az";
import type { CheckResult, LinkInfo } from "@/lib/types";
import { Chip, VERDICT_STYLE, tint } from "./ui";

const SHOWN_LINK_STATUSES: LinkInfo["status"][] = ["lookalike", "suspicious", "shortener", "official"];

export function VerdictCard({ result }: { result: CheckResult }) {
  const { t } = useLang();
  const meta = VERDICT_STYLE[result.verdict];
  const shownLinks = result.links.filter((l) => SHOWN_LINK_STATUSES.includes(l.status));
  const tips = tipsFor(t, result.scheme);

  return (
    <article
      className="overflow-hidden rounded-2xl border border-line bg-surface"
      style={{ boxShadow: `inset 4px 0 0 ${meta.color}` }}
      aria-labelledby="verdict-title"
    >
      <div className="px-5 py-4 sm:px-6" style={{ background: tint(meta.color, 12) }}>
        <div className="flex items-center gap-3">
          <span className="text-4xl leading-none" aria-hidden>{meta.emoji}</span>
          <div className="min-w-0">
            <h2 id="verdict-title" className="text-xl font-bold tracking-tight sm:text-2xl">{t(`verdict.${result.verdict}.title`)}</h2>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              {result.scheme !== "none" && <Chip>📌 {schemeLabel(t, result.scheme)}</Chip>}
              {!result.degraded && <span className="text-xs text-ink2">{t("verdict.confidence", { pct: pct(result.confidence) })}</span>}
            </div>
          </div>
        </div>
      </div>

      <div className="space-y-5 px-5 py-5 sm:px-6">
        {result.explanation_az && <p className="text-base">{result.explanation_az}</p>}

        {result.reasons.length > 0 && (
          <div>
            <h3 className="mb-1.5 text-sm font-semibold">{t("card.why")}</h3>
            <ul className="list-disc space-y-1 pl-5 text-sm text-ink2 marker:text-muted">
              {result.reasons.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </div>
        )}

        {shownLinks.length > 0 && (
          <ul className="space-y-1.5">
            {shownLinks.map((l, i) => (
              <li key={i} className="flex flex-wrap items-center gap-2 text-sm">
                <span aria-hidden>🔗</span>
                <code className="rounded bg-page px-1.5 py-0.5 font-mono text-[13px]">{l.domain}</code>
                <span className="text-ink2">{t(`link.${l.status}` as MessageKey)}</span>
              </li>
            ))}
          </ul>
        )}

        {result.links.filter((l) => l.age_days != null && l.age_days < 90).map((l, i) => (
          <p key={`age-${i}`} className="flex flex-wrap items-center gap-2 text-sm">
            <span aria-hidden>🕒</span>
            <code className="rounded bg-page px-1.5 py-0.5 font-mono text-[13px]">{l.domain}</code>
            <span className="text-ink2">
              {t("link.age_note", { when: l.age_days === 0 ? t("link.age_today") : t("link.age_days", { n: l.age_days ?? 0 }) })}
            </span>
          </p>
        ))}

        {result.actions.length > 0 && (
          <div>
            <h3 className="mb-1.5 text-sm font-semibold">{t("card.actions")}</h3>
            <ol className="list-decimal space-y-1 pl-5 text-sm marker:font-semibold marker:text-ink2">
              {result.actions.map((a, i) => <li key={i}>{a}</li>)}
            </ol>
          </div>
        )}

        {result.verdict !== "safe" && !result.degraded && (
          <div className="rounded-xl bg-page p-3">
            <h3 className="mb-1.5 text-sm font-semibold">{t("card.tips")} <span className="font-normal text-ink2">({tips.title})</span></h3>
            <ul className="list-disc space-y-1 pl-5 text-sm text-ink2 marker:text-muted">
              {tips.flags.map((f, i) => <li key={i}>{f}</li>)}
            </ul>
          </div>
        )}

        {result.degraded && (
          <p className="rounded-lg px-3 py-2 text-sm" style={{ background: tint("var(--warn)", 14) }}>{t("card.degraded")}</p>
        )}

        <p className="border-t border-grid pt-3 text-xs text-ink2">
          {result.provider ? `${t("card.analysis", { provider: result.provider, model: result.model })} ` : ""}
          {t("card.privacy")}
        </p>
      </div>
    </article>
  );
}
