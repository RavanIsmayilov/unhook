"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { az, type MessageKey } from "./messages/az";
import { en } from "./messages/en";
import { ru } from "./messages/ru";

export type Lang = "az" | "en" | "ru";
export const LANGS: { code: Lang; label: string; name: string }[] = [
  { code: "az", label: "AZ", name: "Azərbaycanca" },
  { code: "en", label: "EN", name: "English" },
  { code: "ru", label: "RU", name: "Русский" },
];

/** BCP-47 tags for number formatting. */
export const LOCALES: Record<Lang, string> = { az: "az", en: "en-US", ru: "ru-RU" };

const DICTS: Record<Lang, Record<MessageKey, string>> = { az, en, ru };
const STORAGE_KEY = "unhook-lang";

const isLang = (x: unknown): x is Lang => x === "az" || x === "en" || x === "ru";

/** ?lang=xx wins, then the saved choice, then the browser language (az / ru, otherwise English). */
function detectLang(): Lang {
  try {
    const fromUrl = new URLSearchParams(window.location.search).get("lang");
    if (isLang(fromUrl)) {
      localStorage.setItem(STORAGE_KEY, fromUrl);
      return fromUrl;
    }
    const saved = localStorage.getItem(STORAGE_KEY);
    if (isLang(saved)) return saved;
  } catch {
    /* storage can be blocked: fall through to the browser language */
  }
  const nav = (typeof navigator !== "undefined" ? navigator.language : "").toLowerCase();
  if (nav.startsWith("az")) return "az";
  if (nav.startsWith("ru")) return "ru";
  return "en";
}

type Vars = Record<string, string | number>;
export type TFunction = (key: MessageKey, vars?: Vars) => string;

function format(template: string, vars?: Vars): string {
  return vars ? template.replace(/\{(\w+)\}/g, (m, name) => (name in vars ? String(vars[name]) : m)) : template;
}

interface LangContextValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: TFunction;
}

const LangContext = createContext<LangContextValue>({
  lang: "en",
  setLang: () => {},
  t: (key, vars) => format(en[key] ?? key, vars),
});

export function LangProvider({ children }: { children: ReactNode }) {
  // Static pages are rendered in English first (also what a reader without JavaScript sees); the visitor's language is applied on load.
  const [lang, setLangState] = useState<Lang>("en");

  useEffect(() => setLangState(detectLang()), []);
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
  }, []);

  const t = useCallback<TFunction>((key, vars) => format(DICTS[lang][key] ?? en[key] ?? key, vars), [lang]);
  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export const useLang = () => useContext(LangContext);

// ---- labels that depend on a code coming from the API

const SCHEMES = new Set(["fake_bonus", "bank_impersonation", "fake_job", "delivery_scam", "investment_scam", "other", "none"]);

export function schemeLabel(t: TFunction, scheme: string): string {
  return t(`scheme.${SCHEMES.has(scheme) ? scheme : "other"}` as MessageKey);
}

/** "How to recognize this scam": general advice per scheme. No statistics. */
export function tipsFor(t: TFunction, scheme: string): { title: string; flags: string[] } {
  const s = SCHEMES.has(scheme) && scheme !== "none" ? scheme : "other";
  return { title: t(`tip.${s}.title` as MessageKey), flags: [1, 2, 3].map((i) => t(`tip.${s}.${i}` as MessageKey)) };
}
