"use client";

import QRCode from "qrcode";
import { useEffect, useState } from "react";
import { Notice } from "@/components/ui";

export default function QrPage() {
  const [url, setUrl] = useState("");
  const [png, setPng] = useState<string | null>(null);

  useEffect(() => {
    setUrl(new URLSearchParams(window.location.search).get("u") || window.location.origin);
  }, []);

  useEffect(() => {
    if (!url) return;
    // Always black on white with a quiet zone, whatever the page theme is: scanners need the contrast.
    QRCode.toDataURL(url, { width: 640, margin: 2, errorCorrectionLevel: "M", color: { dark: "#000000", light: "#ffffff" } })
      .then(setPng)
      .catch(() => setPng(null));
  }, [url]);

  const isLocal = /^https?:\/\/(localhost|127\.|192\.168\.|10\.)/.test(url);

  return (
    <div className="mx-auto max-w-md space-y-5 text-center">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Telefonla skan edin</h1>
        <p className="mt-1 text-ink2">Kameranı QR koda tutun və Unhook ilə mesajınızı yoxlayın.</p>
      </div>

      {png ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={png} alt={`QR kod: ${url}`} className="mx-auto aspect-square w-full max-w-sm rounded-2xl border border-line" />
      ) : (
        <div className="mx-auto aspect-square w-full max-w-sm animate-pulse rounded-2xl bg-surface" />
      )}

      <p className="break-all font-mono text-sm text-ink2">{url}</p>

      {isLocal && (
        <Notice tone="warn">
          Bu ünvan yalnız bu komputerdə açılır, telefon onu aça bilməz. Saytı Vercel-ə yüklədikdən sonra həmin ünvanı aşağıya yazın.
        </Notice>
      )}

      <label className="block text-left text-sm">
        <span className="mb-1 block text-ink2">QR kodun ünvanı</span>
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value.trim())}
          placeholder="https://unhook.vercel.app"
          className="w-full rounded-xl border border-line bg-surface px-3 py-2.5 text-base"
        />
      </label>
    </div>
  );
}
