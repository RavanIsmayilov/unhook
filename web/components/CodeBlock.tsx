"use client";

import { useState } from "react";
import { useLang } from "@/lib/i18n";

export function CodeBlock({ code, label }: { code: string; label?: string }) {
  const { t } = useLang();
  const [copied, setCopied] = useState(false);
  return (
    <div className="overflow-hidden rounded-xl border border-line bg-page">
      <div className="flex items-center justify-between border-b border-grid px-3 py-1.5 text-xs text-ink2">
        <span>{label ?? ""}</span>
        <button
          type="button"
          onClick={() => navigator.clipboard.writeText(code).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); }).catch(() => {})}
          className="rounded px-2 py-0.5 hover:bg-surface"
        >
          {copied ? t("code.copied") : t("code.copy")}
        </button>
      </div>
      <pre className="overflow-x-auto p-3 text-[13px] leading-relaxed"><code>{code}</code></pre>
    </div>
  );
}
