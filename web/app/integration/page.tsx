import type { Metadata } from "next";
import Link from "next/link";
import { CodeBlock } from "@/components/CodeBlock";
import { Card } from "@/components/ui";
import { API_URL } from "@/lib/api";

export const metadata: Metadata = { title: "Şirkətlər üçün: Unhook inteqrasiyası" };

const CHECK_RESPONSE = `{
  "verdict": "scam",            // scam | suspicious | safe
  "scheme": "fake_bonus",
  "scheme_az": "Saxta bonus / uduş",
  "confidence": 0.97,
  "reasons": ["Link rəsmi Azercell saytına oxşayır, amma saxtadır", "..."],
  "actions": ["Linkə klikləməyin", "..."],
  "explanation_az": "Bu mesaj Azercell adından istifadə edərək...",
  "links": [{"domain": "bonus-azercell.top", "status": "lookalike"}],
  "degraded": false,            // true: AI cavab verə bilmədi, yalnız linklər yoxlanıldı
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

const ENDPOINTS: [string, string, string][] = [
  ["GET", "/partner/me", "Açarın kimə aid olduğunu və brendini göstərir"],
  ["POST", "/partner/check", "Bir mesajı yoxlayır (mətn və ya şəkil)"],
  ["POST", "/partner/check/batch", "10-a qədər mesajı bir sorğuda yoxlayır"],
  ["GET", "/partner/summary", "Brendiniz üçün rəqəmlər"],
  ["GET", "/partner/campaigns", "Brendinizi təqlid edən kampaniyalar"],
  ["GET", "/partner/blocklist", "Saxta domenlər (JSON, və ya ?format=csv)"],
];

export default function Integration() {
  const api = API_URL;
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Şirkətlər üçün inteqrasiya</h1>
        <p className="mt-2 text-ink2">
          Banklar, mobil operatorlar və dövlət qurumları Unhook-u öz sisteminə qoşa bilər: mesajları yoxlamaq, brendinizi təqlid edən
          kampaniyalardan xəbər tutmaq və saxta domenləri bloklamaq üçün.
        </p>
        <p className="mt-3">
          <Link href="/partner" className="font-medium text-s1 underline underline-offset-2">Tərəfdaş panelinə daxil ol →</Link>
        </p>
      </div>

      <section className="grid gap-3 sm:grid-cols-3" aria-label="İstifadə ssenariləri">
        {[
          ["📱 Mobil operator", "Gələn SMS-lər SMS-gateway-də /partner/check ilə yoxlanılır. Fırıldaq olanlar bloklanır, şübhəlilər etiketlənir. Saxta linklər /partner/blocklist ilə şəbəkədə bağlanır."],
          ["🏦 Bank", "Mobil tətbiqdə “Mesajı yoxla” düyməsi. Fraud komandası brendinin adından gedən kampaniyaları görür və webhook ilə dərhal xəbər tutur."],
          ["🏛 Dövlət qurumu", "Ölkə üzrə kampaniya xəritəsi: hansı brendlər hədəfdir, hansı domenlər təkrarlanır. Bütün brendləri görən açar verilə bilər."],
        ].map(([title, text]) => (
          <Card key={title}>
            <h2 className="font-semibold">{title}</h2>
            <p className="mt-1 text-sm text-ink2">{text}</p>
          </Card>
        ))}
      </section>

      <section className="space-y-3" aria-label="Başlamaq">
        <h2 className="text-xl font-semibold tracking-tight">1. Açar alın</h2>
        <p className="text-sm text-ink2">
          Hər şirkətə ayrıca API açarı verilir və o, yalnız <b className="text-ink">öz brendinizin</b> məlumatına çıxış verir (məsələn,
          Azercell açarı Kapital Bank-ın kampaniyalarını göstərmir). Açar yalnız bir dəfə göstərilir, bizdə yalnız hash-i saxlanılır.
          Hackathon prototipində açarı komanda verir (<code>python partners.py create &quot;Azercell&quot; --brand Azercell</code>).
        </p>
        <h2 className="pt-2 text-xl font-semibold tracking-tight">2. Sorğuya başlıq əlavə edin</h2>
        <CodeBlock label="curl" code={`curl ${api}/partner/me \\\n  -H "X-API-Key: unhook_..."`} />
      </section>

      <section className="space-y-3" aria-label="Endpoint-lər">
        <h2 className="text-xl font-semibold tracking-tight">Endpoint-lər</h2>
        <div className="overflow-x-auto rounded-xl border border-line bg-surface">
          <table className="w-full text-left text-sm">
            <tbody>
              {ENDPOINTS.map(([method, path, desc]) => (
                <tr key={path} className="border-b border-grid last:border-0">
                  <td className="px-3 py-2 font-mono text-xs font-semibold">{method}</td>
                  <td className="px-3 py-2 font-mono text-[13px]">{path}</td>
                  <td className="px-3 py-2 text-ink2">{desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-3" aria-label="Mesajı yoxlamaq">
        <h2 className="text-xl font-semibold tracking-tight">Mesajı yoxlamaq</h2>
        <CodeBlock
          label="curl"
          code={`curl -X POST ${api}/partner/check \\\n  -H "X-API-Key: unhook_..." -H "Content-Type: application/json" \\\n  -d '{"text": "salam, bonusunuz hazirdir: bonus-azercell.top/qazan"}'`}
        />
        <CodeBlock label="cavab" code={CHECK_RESPONSE} />
        <p className="text-sm text-ink2">
          Toplu yoxlama (10-a qədər mesaj, cavablar eyni sırada):
        </p>
        <CodeBlock
          label="curl"
          code={`curl -X POST ${api}/partner/check/batch \\\n  -H "X-API-Key: unhook_..." -H "Content-Type: application/json" \\\n  -d '{"messages": ["mesaj 1", "mesaj 2"]}'`}
        />
      </section>

      <section className="space-y-3" aria-label="Blok siyahısı">
        <h2 className="text-xl font-semibold tracking-tight">Blok siyahısı və kampaniyalar</h2>
        <CodeBlock label="CSV (URL filtrinə qoşmaq üçün)" code={`curl "${api}/partner/blocklist?format=csv" -H "X-API-Key: unhook_..." -o unhook-blocklist.csv`} />
        <CodeBlock label="kampaniyalar" code={`curl ${api}/partner/campaigns -H "X-API-Key: unhook_..."`} />
        <p className="text-sm text-ink2">Siyahı avtomatik yaradılır və insan tərəfindən yoxlanmayıb. Bloklamazdan əvvəl öz komandanız yoxlamalıdır.</p>
      </section>

      <section className="space-y-3" aria-label="Webhook">
        <h2 className="text-xl font-semibold tracking-tight">Webhook: dərhal xəbərdarlıq</h2>
        <p className="text-sm text-ink2">
          Brendinizi təqlid edən fırıldaq aşkarlananda sizin ünvana <code>POST</code> göndərilir (Slack, e-poçt və ya SIEM-ə yönləndirmək üçün).
          Hər sorğu <code>X-Unhook-Signature</code> başlığı ilə imzalanır, ona görə onun bizdən gəldiyini yoxlaya bilərsiniz.
        </p>
        <CodeBlock label="hadisə" code={WEBHOOK_EVENT} />
        <CodeBlock label="imzanı yoxlamaq (Python)" code={VERIFY_SNIPPET} />
      </section>

      <section aria-label="Məxfilik">
        <Card>
          <h2 className="font-semibold">Məxfilik, təhlükəsizlik və hüdudlar</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink2 marker:text-muted">
            <li>Kart nömrələri, telefonlar və birdəfəlik kodlar AI-a göndərilməzdən və saxlanmazdan <b className="text-ink">əvvəl</b> silinir.</li>
            <li>API açarları hash ilə saxlanılır, hər açar yalnız öz brendinə çıxış verir, ləğv edilə bilər.</li>
            <li>
              Bu prototip mesajın (şəxsi məlumatsız) mətnini xarici AI xidmətlərinə (Groq, Gemini) göndərir. Real bank üçün planımız:
              <b className="text-ink"> şirkətin öz serverində işləyən yerli model</b>, beləliklə mesajlar şirkətdən kənara çıxmır.
            </li>
            <li>Bu hackathon prototipidir: xidmət səviyyəsi (SLA), sorğu limiti və audit jurnalı hələ yoxdur.</li>
            <li>AI səhv edə bilər. Nəticə köməkçi siqnaldır, yeganə qərar mənbəyi olmamalıdır.</li>
          </ul>
        </Card>
      </section>
    </div>
  );
}
