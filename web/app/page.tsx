"use client";

import { CheckForm } from "@/components/CheckForm";
import { useLang } from "@/lib/i18n";

export default function Home() {
  const { t } = useLang();
  return (
    <div className="mx-auto max-w-xl">
      <div className="mb-6 text-center sm:mb-8">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("home.title")}</h1>
        <p className="mt-3 text-ink2">{t("home.lead")}</p>
      </div>
      <CheckForm />
      <a href="/challenge" className="mt-6 block rounded-2xl border border-line bg-surface p-4 text-center hover:bg-page">
        <span className="font-semibold">{t("home.challenge_title")}</span>
        <span className="block text-sm text-ink2">{t("home.challenge_sub")}</span>
      </a>
      <p className="mt-4 text-center text-sm text-ink2">
        {t("home.telegram")}{" "}
        <a href="https://t.me/unhook_az_bot" className="font-medium text-s1 underline underline-offset-2">@unhook_az_bot</a>
      </p>
    </div>
  );
}
