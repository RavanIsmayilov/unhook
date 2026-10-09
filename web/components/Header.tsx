"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Yoxla" },
  { href: "/dashboard", label: "Panel" },
  { href: "/results", label: "Nəticələr" },
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
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3">
        <Link href="/" aria-label="Unhook, ana səhifə"><Logo /></Link>
        <nav className="flex gap-1" aria-label="Əsas menyu">
          {LINKS.map((l) => {
            const active = l.href === "/" ? path === "/" : path.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={`rounded-lg px-3 py-1.5 text-sm ${active ? "bg-surface font-semibold shadow-[inset_0_0_0_1px_var(--border)]" : "text-ink2 hover:bg-surface"}`}
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
