"use client";

import { useLang } from "@/lib/i18n";

export function Footer() {
  const { t } = useLang();
  const link = "underline underline-offset-2";
  return (
    <footer className="mx-auto max-w-5xl px-4 pb-10 text-center text-sm text-ink2">
      Unhook · <a href="/challenge" className={link}>{t("footer.challenge")}</a> ·{" "}
      <a href="/integration" className={link}>{t("footer.companies")}</a> ·{" "}
      <a href="/qr" className={link}>{t("footer.qr")}</a> ·{" "}
      <a href="https://t.me/unhook_az_bot" className={link}>{t("footer.telegram")}</a>
    </footer>
  );
}
