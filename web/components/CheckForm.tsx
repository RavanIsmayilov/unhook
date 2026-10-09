"use client";

import { useEffect, useRef, useState } from "react";
import { checkErrorMessage, checkMessage } from "@/lib/api";
import { imageToBase64 } from "@/lib/image";
import type { CheckResult } from "@/lib/types";
import { FeedbackBox } from "./FeedbackBox";
import { VerdictCard } from "./VerdictCard";
import { Notice } from "./ui";

const EXAMPLES = [
  { label: "Saxta bonus", text: "salam, bonusunuz hazirdir: bonus-azercell.top/qazan" },
  { label: "Bank bildirişi", text: "Kapital Bank: 4821 kodu heç kimə verməyin. Ödəniş 25.00 AZN təsdiqləndi." },
  { label: "Rus + AZ qarışıq", text: "Privet, vasha karta zablokirovana, təcili perexodi: bit.ly/3xYz" },
];
const MAX_CHARS = 4000;

export function CheckForm() {
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CheckResult | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!file) return setPreview(null);
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  useEffect(() => {
    if (result || error) resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [result, error]);

  const canSubmit = !loading && (text.trim().length > 0 || file !== null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      let image: string | null = null;
      if (file) {
        try {
          image = await imageToBase64(file);
        } catch {
          setError("Şəkil oxuna bilmədi. Başqa şəkil yoxlayın.");
          return;
        }
      }
      setResult(await checkMessage(text, image));
    } catch (err) {
      setError(checkErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setText("");
    setFile(null);
    setResult(null);
    setError(null);
    if (fileInput.current) fileInput.current.value = "";
  }

  return (
    <div className="space-y-6">
      <form onSubmit={submit} className="space-y-4 rounded-2xl border border-line bg-surface p-4 sm:p-5">
        <div>
          <label htmlFor="message" className="mb-1.5 block text-sm font-semibold">Şübhəli mesaj</label>
          <textarea
            id="message"
            value={text}
            onChange={(e) => setText(e.target.value.slice(0, MAX_CHARS))}
            rows={5}
            placeholder="Mesajı bura yapışdırın (məs. “salam, bonusunuz hazirdir...”)"
            className="w-full resize-y rounded-xl border border-line bg-page px-3 py-2.5 text-base placeholder:text-muted focus:border-s1"
          />
          <div className="mt-1 text-right text-xs text-ink2 tabular-nums">{text.length}/{MAX_CHARS}</div>
        </div>

        <div className="flex flex-wrap items-center gap-2" aria-label="Nümunələr">
          <span className="text-xs text-ink2">Nümunə:</span>
          {EXAMPLES.map((ex) => (
            <button
              key={ex.label}
              type="button"
              onClick={() => setText(ex.text)}
              className="rounded-full border border-line px-3 py-1 text-xs text-ink2 hover:bg-page"
            >
              {ex.label}
            </button>
          ))}
        </div>

        <div>
          <input
            ref={fileInput}
            id="screenshot"
            type="file"
            accept="image/*"
            className="sr-only"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          {preview ? (
            <div className="flex items-center gap-3 rounded-xl border border-line p-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={preview} alt="Seçilmiş ekran görüntüsü" className="h-16 w-16 rounded-lg object-cover" />
              <span className="min-w-0 flex-1 truncate text-sm">{file?.name}</span>
              <button
                type="button"
                onClick={() => { setFile(null); if (fileInput.current) fileInput.current.value = ""; }}
                className="rounded-lg border border-line px-3 py-1.5 text-sm hover:bg-page"
              >
                Sil
              </button>
            </div>
          ) : (
            <label
              htmlFor="screenshot"
              className="flex min-h-12 cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-axis px-4 py-3 text-sm text-ink2 hover:bg-page focus-within:outline-2"
            >
              <span aria-hidden>📷</span> Ekran görüntüsü əlavə et
            </label>
          )}
        </div>

        <button
          type="submit"
          disabled={!canSubmit}
          className="flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-s1 px-4 py-3 text-base font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" aria-hidden />
              Yoxlayıram...
            </>
          ) : (
            "Yoxla"
          )}
        </button>
      </form>

      <div ref={resultRef} aria-live="polite" className="scroll-mt-20 space-y-4">
        {error && <Notice tone="warn">{error}</Notice>}
        {result && (
          <>
            <VerdictCard result={result} />
            {result.report_id !== null && <FeedbackBox key={result.report_id} reportId={result.report_id} />}
            <button type="button" onClick={reset} className="w-full rounded-xl border border-line px-4 py-3 text-sm font-medium hover:bg-surface">
              Başqa mesaj yoxla
            </button>
          </>
        )}
      </div>
    </div>
  );
}
