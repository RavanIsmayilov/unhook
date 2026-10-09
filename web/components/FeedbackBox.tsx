"use client";

import { useState } from "react";
import { sendFeedback } from "@/lib/api";
import { useLang } from "@/lib/i18n";

type Step = "ask" | "which" | "done" | "error";

/** "Was this answer right?" Disagreements become candidate test cases on the dashboard. */
export function FeedbackBox({ reportId }: { reportId: number }) {
  const { t } = useLang();
  const [step, setStep] = useState<Step>("ask");
  const [busy, setBusy] = useState(false);

  async function send(agrees: boolean, suggested?: "scam" | "safe") {
    setBusy(true);
    try {
      await sendFeedback(reportId, agrees, suggested);
      setStep("done");
    } catch {
      setStep("error");
    } finally {
      setBusy(false);
    }
  }

  const btn = "min-h-11 rounded-xl border border-line px-4 py-2 text-sm font-medium hover:bg-page disabled:opacity-50";

  return (
    <div className="rounded-2xl border border-line bg-surface p-4" aria-live="polite">
      {step === "ask" && (
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium">{t("fb.ask")}</span>
          <button type="button" disabled={busy} onClick={() => send(true)} className={btn}>{t("fb.yes")}</button>
          <button type="button" disabled={busy} onClick={() => setStep("which")} className={btn}>{t("fb.no")}</button>
        </div>
      )}
      {step === "which" && (
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium">{t("fb.which")}</span>
          <button type="button" disabled={busy} onClick={() => send(false, "scam")} className={btn}>{t("fb.scam")}</button>
          <button type="button" disabled={busy} onClick={() => send(false, "safe")} className={btn}>{t("fb.safe")}</button>
        </div>
      )}
      {step === "done" && <p className="text-sm">{t("fb.done")}</p>}
      {step === "error" && <p className="text-sm text-ink2">{t("fb.error")}</p>}
    </div>
  );
}
