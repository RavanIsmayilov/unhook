import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { Header } from "@/components/Header";
import "./globals.css";

export const metadata: Metadata = {
  title: "Unhook: fırıldaqçıya tutulmadan əvvəl xilas ol",
  description: "Şübhəli mesajı və ya ekran görüntüsünü yoxlayın. Azərbaycan dilində, translitlə və rus qarışıq mətnlər üçün fırıldaq detektoru.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="az">
      <body>
        <Header />
        <main className="mx-auto max-w-5xl px-4 pb-10 pt-6 sm:pt-10">{children}</main>
        <footer className="mx-auto max-w-5xl px-4 pb-10 text-center text-sm text-ink2">
          Unhook · <a href="/qr" className="underline underline-offset-2">QR kod</a> ·{" "}
          <a href="https://t.me/unhook_az_bot" className="underline underline-offset-2">Telegram bot</a>
        </footer>
      </body>
    </html>
  );
}
