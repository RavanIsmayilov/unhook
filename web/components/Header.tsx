"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LANGS, useLang } from "@/lib/i18n";
import type { MessageKey } from "@/lib/messages/az";

const LINKS: { href: string; key: MessageKey; match: string[] }[] = [
  { href: "/", key: "nav.check", match: ["/"] },
  { href: "/radar", key: "nav.radar", match: ["/radar"] },
  { href: "/dashboard", key: "nav.panel", match: ["/dashboard"] },
  { href: "/results", key: "nav.results", match: ["/results"] },
  { href: "/integration", key: "nav.companies", match: ["/integration", "/partner"] },
];

export function Logo() {
  return (
    <span className="flex items-center gap-2 text-lg font-bold tracking-tight">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
        <path d="M12 3v9.5a4 4 0 1 1-4-4" stroke="var(--series-1)" strokeWidth="2.4" strokeLinecap="round" />
        <circle cx="12" cy="3" r="1.6" fill="var(--series-1)" />
      </svg>
      Unhook
    </span>
  );
}

function LanguageSwitch() {
  const { lang, setLang, t } = useLang();
  return (
    <div role="group" aria-label={t("lang.aria")} className="flex rounded-lg border border-line bg-surface p-0.5 text-xs font-semibold">
      {LANGS.map((l) => (
        <button
          key={l.code}
          type="button"
          onClick={() => setLang(l.code)}
          aria-pressed={lang === l.code}
          title={l.name}
          className={`min-w-9 rounded-md px-2 py-1 ${lang === l.code ? "bg-s1 text-white" : "text-ink2 hover:bg-page"}`}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}

export function Header() {
  const path = usePathname();
  const { t } = useLang();
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-page/90 backdrop-blur">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-3 gap-y-1 px-4 py-2.5">
        <Link href="/" aria-label={t("nav.home")}><Logo /></Link>
        {/* On a phone the menu drops to its own row so all five links stay readable; the language switch stays next to the logo. */}
        <div className="order-2 sm:order-3"><LanguageSwitch /></div>
        <nav className="order-last flex w-full gap-1 sm:order-2 sm:w-auto" aria-label={t("nav.aria")}>
          {LINKS.map((l) => {
            const active = l.match.some((m) => (m === "/" ? path === "/" : path.startsWith(m)));
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={`flex-1 rounded-lg px-1.5 py-1.5 text-center text-[13px] sm:flex-none sm:px-3 sm:text-sm ${active ? "bg-surface font-semibold shadow-[inset_0_0_0_1px_var(--border)]" : "text-ink2 hover:bg-surface"}`}
              >
                {t(l.key)}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
