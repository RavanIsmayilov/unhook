"use client";

import { useState } from "react";
import { sendFeedback } from "@/lib/api";

type Step = "ask" | "which" | "done" | "error";

/** "Was this answer right?" Disagreements become candidate test cases on the dashboard. */
export function FeedbackBox({ reportId }: { reportId: number }) {
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
          <span className="text-sm font-medium">Bu cavab düzgündür?</span>
          <button type="button" disabled={busy} onClick={() => send(true)} className={btn}>👍 Bəli</button>
          <button type="button" disabled={busy} onClick={() => setStep("which")} className={btn}>👎 Xeyr</button>
        </div>
      )}
      {step === "which" && (
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium">Əslində bu mesaj:</span>
          <button type="button" disabled={busy} onClick={() => send(false, "scam")} className={btn}>🔴 Fırıldaqdır</button>
          <button type="button" disabled={busy} onClick={() => send(false, "safe")} className={btn}>🟢 Təhlükəsizdir</button>
        </div>
      )}
      {step === "done" && <p className="text-sm">Təşəkkür edirik! Bu, sistemi yaxşılaşdırmaq üçün test nümunəsi kimi istifadə olunacaq.</p>}
      {step === "error" && <p className="text-sm text-ink2">Geri bildirim göndərilə bilmədi. Bir az sonra yenidən cəhd edin.</p>}
    </div>
  );
}
