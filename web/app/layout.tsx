import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";
import { LangProvider } from "@/lib/i18n";
import "./globals.css";

export const metadata: Metadata = {
  title: "Unhook: get unhooked before you get scammed",
  description:
    "Check a suspicious message or screenshot. A scam detector for Azerbaijani, translit and mixed Azerbaijani + Russian text, with a live campaign view for banks and telecoms.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <LangProvider>
          <Header />
          <main className="mx-auto max-w-5xl px-4 pb-10 pt-6 sm:pt-10">{children}</main>
          <Footer />
        </LangProvider>
      </body>
    </html>
  );
}
