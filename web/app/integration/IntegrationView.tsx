"use client";

import Link from "next/link";
import { CodeBlock } from "@/components/CodeBlock";
import { Card } from "@/components/ui";
import { API_URL } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import type { MessageKey } from "@/lib/messages/az";

const CHECK_RESPONSE = `{
  "verdict": "scam",            // scam | suspicious | safe
  "scheme": "fake_bonus",
  "scheme_az": "Saxta bonus / uduş",
  "confidence": 0.97,
  "reasons": ["The link imitates the official Azercell site", "..."],
  "actions": ["Do not click the link", "..."],
  "explanation_az": "This message pretends to be Azercell...",   // written in the requested "lang"
  "links": [{"domain": "bonus-azercell.top", "status": "lookalike"}],
  "degraded": false,            // true: the AI could not answer, only the links were checked
  "report_id": 123
}`;

const WEBHOOK_EVENT = `{
  "event": "report.flagged",
  "sent_at": "2026-10-09T12:30:00+00:00",
  "report": {
    "id": 123,
    "verdict": "scam",
    "scheme": "fake_bonus",
    "scheme_az": "Saxta bonus / uduş",
    "confidence": 0.97,
    "text_redacted": "salam, bonusunuz hazirdir: bonus-azercell.top/qazan",
    "domains": ["bonus-azercell.top"],
    "brands": ["Azercell"]
  }
}`;

const VERIFY_SNIPPET = `import hashlib, hmac

def is_from_unhook(raw_body: bytes, signature_header: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)   # header: X-Unhook-Signature`;

const ENDPOINTS: [string, string, MessageKey][] = [
  ["GET", "/partner/me", "int.ep.me"],
  ["POST", "/partner/check", "int.ep.check"],
  ["POST", "/partner/check/batch", "int.ep.batch"],
  ["GET", "/partner/summary", "int.ep.summary"],
  ["GET", "/partner/campaigns", "int.ep.campaigns"],
  ["GET", "/partner/blocklist", "int.ep.blocklist"],
];

const SCENARIOS: { title: MessageKey; text: MessageKey }[] = [
  { title: "int.scen1.title", text: "int.scen1.text" },
  { title: "int.scen2.title", text: "int.scen2.text" },
  { title: "int.scen3.title", text: "int.scen3.text" },
];

const PRIVACY: MessageKey[] = ["int.priv.1", "int.priv.2", "int.priv.3", "int.priv.4", "int.priv.5"];

export function IntegrationView() {
  const { t } = useLang();
  const api = API_URL;
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{t("int.title")}</h1>
        <p className="mt-2 text-ink2">{t("int.lead")}</p>
        <p className="mt-3">
          <Link href="/partner" className="font-medium text-s1 underline underline-offset-2">{t("int.panel_link")}</Link>
        </p>
      </div>

      <section className="grid gap-3 sm:grid-cols-3" aria-label={t("int.scen.aria")}>
        {SCENARIOS.map((s) => (
          <Card key={s.title}>
            <h2 className="font-semibold">{t(s.title)}</h2>
            <p className="mt-1 text-sm text-ink2">{t(s.text)}</p>
          </Card>
        ))}
      </section>

      <section className="space-y-3" aria-label={t("int.start.aria")}>
        <h2 className="text-xl font-semibold tracking-tight">{t("int.step1")}</h2>
        <p className="text-sm text-ink2">{t("int.step1.text")}</p>
        <h2 className="pt-2 text-xl font-semibold tracking-tight">{t("int.step2")}</h2>
        <CodeBlock label="curl" code={`curl ${api}/partner/me \\\n  -H "X-API-Key: unhook_..."`} />
      </section>

      <section className="space-y-3" aria-label={t("int.endpoints.aria")}>
        <h2 className="text-xl font-semibold tracking-tight">{t("int.endpoints.title")}</h2>
        <div className="overflow-x-auto rounded-xl border border-line bg-surface">
          <table className="w-full text-left text-sm">
            <tbody>
              {ENDPOINTS.map(([method, path, desc]) => (
                <tr key={path} className="border-b border-grid last:border-0">
                  <td className="px-3 py-2 font-mono text-xs font-semibold">{method}</td>
                  <td className="px-3 py-2 font-mono text-[13px]">{path}</td>
                  <td className="px-3 py-2 text-ink2">{t(desc)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-3" aria-label={t("int.check.aria")}>
        <h2 className="text-xl font-semibold tracking-tight">{t("int.check.title")}</h2>
        <CodeBlock
          label="curl"
          code={`curl -X POST ${api}/partner/check \\\n  -H "X-API-Key: unhook_..." -H "Content-Type: application/json" \\\n  -d '{"text": "salam, bonusunuz hazirdir: bonus-azercell.top/qazan", "lang": "en"}'`}
        />
        <p className="text-sm text-ink2">{t("int.check.lang")}</p>
        <CodeBlock label={t("int.check.response")} code={CHECK_RESPONSE} />
        <p className="text-sm text-ink2">{t("int.check.batch")}</p>
        <CodeBlock
          label="curl"
          code={`curl -X POST ${api}/partner/check/batch \\\n  -H "X-API-Key: unhook_..." -H "Content-Type: application/json" \\\n  -d '{"messages": ["message 1", "message 2"]}'`}
        />
      </section>

      <section className="space-y-3" aria-label={t("int.bl.aria")}>
        <h2 className="text-xl font-semibold tracking-tight">{t("int.bl.title")}</h2>
        <CodeBlock label={t("int.bl.csv")} code={`curl "${api}/partner/blocklist?format=csv" -H "X-API-Key: unhook_..." -o unhook-blocklist.csv`} />
        <CodeBlock label={t("int.bl.campaigns")} code={`curl ${api}/partner/campaigns -H "X-API-Key: unhook_..."`} />
        <p className="text-sm text-ink2">{t("int.bl.note")}</p>
      </section>

      <section className="space-y-3" aria-label={t("int.hook.aria")}>
        <h2 className="text-xl font-semibold tracking-tight">{t("int.hook.title")}</h2>
        <p className="text-sm text-ink2">{t("int.hook.text")}</p>
        <CodeBlock label={t("int.hook.event")} code={WEBHOOK_EVENT} />
        <CodeBlock label={t("int.hook.verify")} code={VERIFY_SNIPPET} />
      </section>

      <section aria-label={t("int.priv.aria")}>
        <Card>
          <h2 className="font-semibold">{t("int.priv.title")}</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink2 marker:text-muted">
            {PRIVACY.map((k) => <li key={k}>{t(k)}</li>)}
          </ul>
        </Card>
      </section>
    </div>
  );
}
