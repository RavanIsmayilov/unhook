"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Yoxla", match: ["/"] },
  { href: "/radar", label: "Radar", match: ["/radar"] },
  { href: "/dashboard", label: "Panel", match: ["/dashboard"] },
  { href: "/results", label: "Nəticələr", match: ["/results"] },
  { href: "/integration", label: "Şirkətlər", match: ["/integration", "/partner"] },
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

export function Header() {
  const path = usePathname();
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-page/90 backdrop-blur">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-3 gap-y-1 px-4 py-2.5">
        <Link href="/" aria-label="Unhook, ana səhifə"><Logo /></Link>
        {/* On a phone the menu drops to its own row so all four links stay readable. */}
        <nav className="order-last flex w-full gap-1 sm:order-none sm:w-auto" aria-label="Əsas menyu">
          {LINKS.map((l) => {
            const active = l.match.some((m) => (m === "/" ? path === "/" : path.startsWith(m)));
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={`flex-1 rounded-lg px-1.5 py-1.5 text-center text-[13px] sm:flex-none sm:px-3 sm:text-sm ${active ? "bg-surface font-semibold shadow-[inset_0_0_0_1px_var(--border)]" : "text-ink2 hover:bg-surface"}`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
